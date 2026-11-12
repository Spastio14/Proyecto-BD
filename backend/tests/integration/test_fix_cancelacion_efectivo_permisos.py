"""
Pruebas de regresión para los bugs corregidos en fix-cancelacion-efectivo-permisos.

Bugs cubiertos:
  Bug 1 – puede_cancelar bloqueado por transacciones RECHAZADAS (portal.py + orders.py)
  Bug 2 – Verificación de PEDIDO_GESTIONAR en la cadena de autorización del admin
  Bug 3 – Pedidos completamente pagados aparecen en cash_receivable_orders (payments.py)
  Bug 4 – Formulario .order-cancel-form sin listener en showOrderDetail (solo verificación
           del contrato de API, ya que el fix es frontend-only)

Convenciones:
  - session / customer / employee: fixtures de conftest.py
  - create_order / add_client: helpers de tests/helpers.py
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.exceptions import Conflict
from app.models.entities import (
    AplicacionTransaccionHito,
    AsignacionRol,
    Empleado,
    HitoPago,
    Permiso,
    Rol,
    RolPermiso,
    Transaccion,
)
from app.services.orders import OrderService
from app.services.payments import PaymentService
from app.services.portal import PortalService
from tests.helpers import add_client, create_order

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Helpers locales
# ---------------------------------------------------------------------------


def _transfer(session, order, principal, amount, scope="TOTAL"):
    return PaymentService().report(
        session,
        order_id=order.id_pedido,
        amount=Decimal(amount),
        payment_scope=scope,
        idempotency_key=uuid4(),
        method="TRANSFERENCIA",
        principal=principal,
        bank_origin="BANCO TEST",
        reference=f"REF-{uuid4().hex[:8]}",
    )


def _cash(session, order, principal, amount, register, scope="TOTAL"):
    return PaymentService().register_cash_payment(
        session,
        order_id=order.id_pedido,
        cash_register_id=register.id_caja,
        amount=Decimal(amount),
        payment_scope=scope,
        idempotency_key=uuid4(),
        principal=principal,
    )


# ---------------------------------------------------------------------------
# BUG 1 — Cancelación del cliente: transacciones RECHAZADAS no deben bloquear
# ---------------------------------------------------------------------------


class TestCancelacionClienteTransaccionRechazada:
    """Bug 1: orders.py cancel() y portal.py _serialize_order()."""

    def test_puede_cancelar_true_sin_transacciones(self, session, customer):
        """Pedido recién creado (sin ninguna transacción) debe poder cancelarse."""
        order = create_order(session, customer)
        portal = PortalService._serialize_order(session, order=order, principal=customer)
        assert portal.puede_cancelar is True
        assert portal.motivo_bloqueo_cancelacion is None

    def test_puede_cancelar_false_con_transferencia_pendiente(self, session, customer):
        """Transferencia PENDIENTE de verificación debe bloquear la cancelación."""
        order = create_order(session, customer)
        _transfer(session, order, customer, "90.00")
        portal = PortalService._serialize_order(session, order=order, principal=customer)
        assert portal.puede_cancelar is False
        assert "revisión administrativa" in portal.motivo_bloqueo_cancelacion

    def test_puede_cancelar_false_con_transferencia_verificada(self, session, customer, employee):
        """Transferencia VERIFICADA debe bloquear la cancelación."""
        order = create_order(session, customer)
        t = _transfer(session, order, customer, "90.00")
        PaymentService().confirm(session, payment_id=t.id_transaccion, principal=employee)
        portal = PortalService._serialize_order(session, order=order, principal=customer)
        assert portal.puede_cancelar is False

    def test_puede_cancelar_true_con_sola_transferencia_rechazada(self, session, customer, employee):
        """
        Única transacción existente es RECHAZADA → el cliente DEBE poder cancelar.
        Este es el bug principal corregido.
        """
        order = create_order(session, customer)
        t = _transfer(session, order, customer, "90.00")
        PaymentService().reject(
            session,
            payment_id=t.id_transaccion,
            principal=employee,
            reason="No corresponde",
        )
        # La transacción existe en BD pero con estado RECHAZADO
        txn = session.get(Transaccion, t.id_transaccion)
        assert txn.estado_verificacion == "RECHAZADO"

        portal = PortalService._serialize_order(session, order=order, principal=customer)
        assert portal.puede_cancelar is True, (
            "Una transacción RECHAZADA no debe bloquear la cancelación del cliente"
        )
        assert portal.motivo_bloqueo_cancelacion is None

    def test_cancel_service_permite_cancelar_tras_rechazo(self, session, customer, employee):
        """
        orders.py cancel() no debe lanzar Conflict cuando solo hay
        transacciones RECHAZADAS y los hitos siguen PENDIENTE.
        """
        order = create_order(session, customer)
        t = _transfer(session, order, customer, "90.00")
        PaymentService().reject(
            session,
            payment_id=t.id_transaccion,
            principal=employee,
            reason="No localizado",
        )
        # No debe lanzar excepción
        cancelled = OrderService().cancel(
            session,
            order_id=order.id_pedido,
            principal=customer,
            reason="Ya no necesito el pedido",
        )
        assert cancelled.estado == "CANCELADO"

    def test_cancel_service_bloquea_si_hay_rechazada_y_pendiente(
        self, session, customer, employee
    ):
        """
        Si coexiste una transferencia RECHAZADA y una PENDIENTE, la cancelación
        debe bloquearse (la PENDIENTE es dinero en tránsito).
        """
        order = create_order(session, customer)
        t1 = _transfer(session, order, customer, "45.00")
        PaymentService().reject(
            session, payment_id=t1.id_transaccion, principal=employee, reason="Falsa"
        )
        # Segunda transferencia, pendiente
        _transfer(session, order, customer, "45.00")
        with pytest.raises(Conflict, match="revisión administrativa"):
            OrderService().cancel(
                session, order_id=order.id_pedido, principal=customer, reason="Intento"
            )

    def test_puede_cancelar_false_si_hito_pagado_aunque_no_hay_transaccion_activa(
        self, session, customer, employee
    ):
        """
        Si el hito está marcado PAGADO (caso legacy), debe bloquear igualmente
        aunque no haya transacciones PENDIENTE/VERIFICADO.
        """
        order = create_order(session, customer)
        t = _transfer(session, order, customer, "90.00")
        PaymentService().confirm(session, payment_id=t.id_transaccion, principal=employee)
        # Simular estado inconsistente: anular la transacción pero dejar hito PAGADO
        t_obj = session.get(Transaccion, t.id_transaccion)
        t_obj.estado_verificacion = "RECHAZADO"
        session.flush()
        # El hito sigue PAGADO → debe bloquear
        hito = session.get(HitoPago, (order.id_pedido, 1))
        assert hito.estado == "PAGADO"
        portal = PortalService._serialize_order(session, order=order, principal=customer)
        assert portal.puede_cancelar is False


# ---------------------------------------------------------------------------
# BUG 2 — Verificación de permisos PEDIDO_GESTIONAR para el rol ADMINISTRADOR
# ---------------------------------------------------------------------------


class TestPermisosAdministrador:
    """Bug 2: PEDIDO_GESTIONAR debe estar asignado al rol ADMINISTRADOR en el seed."""

    def test_permiso_pedido_gestionar_existe_en_catalogo(self, session):
        """El permiso PEDIDO_GESTIONAR debe estar registrado."""
        permiso = session.scalar(
            select(Permiso).where(Permiso.codigo_permiso == "PEDIDO_GESTIONAR")
        )
        assert permiso is not None, "PEDIDO_GESTIONAR no existe en la tabla permiso"

    def test_rol_administrador_existe_y_activo(self, session):
        """El rol ADMINISTRADOR debe existir y estar activo."""
        rol = session.scalar(select(Rol).where(Rol.nombre == "ADMINISTRADOR"))
        assert rol is not None, "El rol ADMINISTRADOR no existe"
        assert rol.estado == "ACTIVO", f"El rol ADMINISTRADOR tiene estado: {rol.estado}"

    def test_administrador_tiene_pedido_gestionar(self, session):
        """
        ADMINISTRADOR debe tener PEDIDO_GESTIONAR en rol_permiso.
        Si falla, el formulario 'Gestionar cancelación' nunca aparecerá
        aunque el usuario esté correctamente autenticado.
        """
        rp = session.scalar(
            select(RolPermiso)
            .join(Rol, Rol.id_rol == RolPermiso.id_rol)
            .join(Permiso, Permiso.id_permiso == RolPermiso.id_permiso)
            .where(Rol.nombre == "ADMINISTRADOR", Permiso.codigo_permiso == "PEDIDO_GESTIONAR")
        )
        assert rp is not None, (
            "PEDIDO_GESTIONAR NO está asignado al rol ADMINISTRADOR. "
            "Ejecutar el seed 003_roles_permisos_fase_4_2.sql para corregirlo."
        )

    def test_administrador_tiene_pago_verificar(self, session):
        """ADMINISTRADOR debe tener PAGO_VERIFICAR (necesario para cobros en efectivo)."""
        rp = session.scalar(
            select(RolPermiso)
            .join(Rol, Rol.id_rol == RolPermiso.id_rol)
            .join(Permiso, Permiso.id_permiso == RolPermiso.id_permiso)
            .where(Rol.nombre == "ADMINISTRADOR", Permiso.codigo_permiso == "PAGO_VERIFICAR")
        )
        assert rp is not None, "PAGO_VERIFICAR NO está asignado al rol ADMINISTRADOR."

    def test_identity_endpoint_incluye_permiso_para_empleado_admin(
        self, api_client_factory, session
    ):
        """
        El endpoint /auth/me debe devolver permisos incluyendo PEDIDO_GESTIONAR
        para un empleado con rol ADMINISTRADOR activo.
        Bug 2: si falta, el frontend evalúa permitted('PEDIDO_GESTIONAR') → false.
        """
        from datetime import UTC, datetime

        from app.models.entities import AsignacionRol, Empleado, Persona

        # Crear empleado con rol ADMINISTRADOR
        persona = Persona(
            nombres="Admin",
            apellidos="Test",
            correo_electronico=f"admin-{uuid4().hex[:6]}@test.test",
        )
        session.add(persona)
        session.flush()
        empleado = Empleado(
            id_persona=persona.id_persona,
            codigo_empleado=f"EMP-{uuid4().hex[:6]}",
            fecha_ingreso=datetime.now(UTC),
            estado_laboral="ACTIVO",
            capacidad_maxima_asignaciones=10,
        )
        session.add(empleado)
        session.flush()
        rol = session.scalar(select(Rol).where(Rol.nombre == "ADMINISTRADOR"))
        assert rol is not None
        session.add(
            AsignacionRol(
                id_empleado=persona.id_persona,
                id_rol=rol.id_rol,
                fecha_asignacion=datetime.now(UTC),
                fecha_finalizacion=None,
                estado="ACTIVA",
            )
        )
        session.commit()

        from app.core.security import Principal

        admin_principal = Principal(persona_id=persona.id_persona, origin="EMPLEADO")
        client = api_client_factory(admin_principal)
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert "PEDIDO_GESTIONAR" in data["permisos"], (
            f"PEDIDO_GESTIONAR no está en los permisos devueltos: {data['permisos']}"
        )


# ---------------------------------------------------------------------------
# BUG 3 — Recepción de efectivo: pedidos completamente pagados no deben aparecer
# ---------------------------------------------------------------------------


class TestCobrosEfectivoPedidosPagados:
    """Bug 3: cash_receivable_orders() no debe listar pedidos completamente pagados."""

    def test_pedido_sin_pago_aparece_disponible(self, session, customer, employee):
        """Pedido recién creado debe aparecer como disponible para cobro en efectivo."""
        order = create_order(session, customer)
        register = PaymentService().open_cash_register(
            session, opening_amount=Decimal("0"), principal=employee
        )
        disponibles = PaymentService.cash_receivable_orders(session, employee)
        ids = [o["id_pedido"] for o in disponibles]
        assert order.id_pedido in ids
        PaymentService().close_cash_register(
            session, cash_register_id=register.id_caja,
            closing_amount=Decimal("0"), principal=employee
        )

    def test_pedido_completamente_pagado_no_aparece(self, session, customer, employee):
        """
        Pedido cuyo total está completamente verificado NO debe aparecer en
        cash_receivable_orders. Este es el bug principal corregido.
        """
        order = create_order(session, customer)
        register = PaymentService().open_cash_register(
            session, opening_amount=Decimal("0"), principal=employee
        )
        # Pagar el total completo en efectivo
        _cash(session, order, employee, str(order.total_pedido), register)

        summary = PaymentService.summary(session, order_id=order.id_pedido, principal=employee)
        assert summary["completamente_pagado"] is True, "El pedido debería estar completamente pagado"

        disponibles = PaymentService.cash_receivable_orders(session, employee)
        ids = [o["id_pedido"] for o in disponibles]
        assert order.id_pedido not in ids, (
            "Un pedido completamente pagado NO debe aparecer en la lista de cobros en efectivo"
        )
        PaymentService().close_cash_register(
            session, cash_register_id=register.id_caja,
            closing_amount=order.total_pedido, principal=employee
        )

    def test_pedido_parcialmente_pagado_aparece(self, session, customer, employee):
        """
        Pedido con anticipo verificado pero saldo pendiente SÍ debe aparecer
        (conservar cobros mixtos efectivo + transferencia).
        """
        order = create_order(session, customer)
        order.total_pedido = Decimal("180.00")
        hito1 = session.get(HitoPago, (order.id_pedido, 1))
        hito2 = session.get(HitoPago, (order.id_pedido, 2))
        hito1.monto_exigido = Decimal("90.00")
        hito2.monto_exigido = Decimal("90.00")
        session.flush()

        register = PaymentService().open_cash_register(
            session, opening_amount=Decimal("0"), principal=employee
        )
        # Pagar solo el anticipo
        _cash(session, order, employee, "90.00", register, scope="ANTICIPO")

        summary = PaymentService.summary(session, order_id=order.id_pedido, principal=employee)
        assert summary["completamente_pagado"] is False
        assert summary["disponible_reportar"] > Decimal("0")

        disponibles = PaymentService.cash_receivable_orders(session, employee)
        ids = [o["id_pedido"] for o in disponibles]
        assert order.id_pedido in ids, (
            "Un pedido con saldo pendiente debe aparecer en la lista de cobros en efectivo"
        )
        PaymentService().close_cash_register(
            session, cash_register_id=register.id_caja,
            closing_amount=Decimal("90.00"), principal=employee
        )

    def test_transaccion_verificada_sin_aplicacion_no_infla_disponible(
        self, session, customer, employee
    ):
        """
        Una transacción VERIFICADA legacy sin AplicacionTransaccionHito
        debe seguir siendo contada por _verified_for_order() (usa TRANSACCION directa)
        y el pedido no debe aparecer como cobrable si el total ya está cubierto.
        """
        from datetime import UTC, datetime

        order = create_order(session, customer)
        total = order.total_pedido

        # Insertar transacción legacy directamente (sin tabla de aplicaciones)
        txn = Transaccion(
            id_pedido=order.id_pedido,
            numero_hito=1,
            id_empleado_verificador=employee.persona_id,
            id_transaccion_compensada=None,
            id_reembolso=None,
            fecha_hora=datetime.now(UTC),
            tipo_transaccion="PAGO",
            monto_con_signo=total,
            metodo_pago="EFECTIVO",
            banco_origen=None,
            banco_receptor=None,
            referencia_bancaria=None,
            estado_verificacion="VERIFICADO",
            fecha_verificacion=datetime.now(UTC),
            clave_idem=uuid4(),
        )
        session.add(txn)
        session.flush()
        # Verificar que NO hay AplicacionTransaccionHito
        apps = list(
            session.scalars(
                select(AplicacionTransaccionHito).where(
                    AplicacionTransaccionHito.id_transaccion == txn.id_transaccion
                )
            )
        )
        assert len(apps) == 0, "Esta prueba requiere que no haya aplicaciones de hito"

        summary = PaymentService.summary(session, order_id=order.id_pedido, principal=employee)
        # _verified_for_order suma la TRANSACCION directa → total cubierto
        assert summary["total_verificado"] == total
        assert summary["completamente_pagado"] is True
        assert summary["disponible_reportar"] == Decimal("0.00")

        disponibles = PaymentService.cash_receivable_orders(session, employee)
        ids = [o["id_pedido"] for o in disponibles]
        assert order.id_pedido not in ids, (
            "Un pedido cuya suma verificada (TRANSACCION) cubre el total "
            "no debe aparecer en la lista de cobros en efectivo"
        )

    def test_cobro_en_efectivo_rechaza_si_pedido_completamente_pagado(
        self, session, customer, employee
    ):
        """
        register_cash_payment() debe rechazar el cobro si el pedido ya está
        completamente pagado (disponible_reportar == 0).
        """
        order = create_order(session, customer)
        register = PaymentService().open_cash_register(
            session, opening_amount=Decimal("0"), principal=employee
        )
        # Pagar el total completo
        _cash(session, order, employee, str(order.total_pedido), register)

        # Intentar cobrar más
        with pytest.raises(Conflict, match="disponible"):
            _cash(session, order, employee, "1.00", register)

        PaymentService().close_cash_register(
            session, cash_register_id=register.id_caja,
            closing_amount=order.total_pedido, principal=employee
        )

    def test_cobro_mixto_transferencia_efectivo_sigue_funcionando(
        self, session, customer, employee
    ):
        """
        La corrección del Bug 3 no debe romper los abonos mixtos:
        anticipo por transferencia + saldo en efectivo.
        """
        order = create_order(session, customer)
        order.total_pedido = Decimal("180.00")
        hito1 = session.get(HitoPago, (order.id_pedido, 1))
        hito2 = session.get(HitoPago, (order.id_pedido, 2))
        hito1.monto_exigido = Decimal("90.00")
        hito2.monto_exigido = Decimal("90.00")
        session.flush()

        # Anticipo por transferencia
        t = _transfer(session, order, customer, "90.00", "ANTICIPO")
        PaymentService().confirm(session, payment_id=t.id_transaccion, principal=employee)

        # Saldo en efectivo
        register = PaymentService().open_cash_register(
            session, opening_amount=Decimal("0"), principal=employee
        )
        _cash(session, order, employee, "90.00", register, scope="SALDO")

        summary = PaymentService.summary(session, order_id=order.id_pedido, principal=employee)
        assert summary["total_verificado"] == Decimal("180.00")
        assert summary["completamente_pagado"] is True
        assert summary["saldo_pendiente"] == Decimal("0.00")
        assert order.estado == "PAGADO"

        PaymentService().close_cash_register(
            session, cash_register_id=register.id_caja,
            closing_amount=Decimal("90.00"), principal=employee
        )

    def test_pedido_200_sin_pagos_disponibilidad_200(self, session, customer, employee):
        """Pedido de C$200 sin pagos: disponibilidad C$200 tanto en summary como en selector."""
        order = create_order(session, customer)
        order.total_pedido = Decimal("200.00")
        h1 = session.get(HitoPago, (order.id_pedido, 1))
        h2 = session.get(HitoPago, (order.id_pedido, 2))
        h1.monto_exigido = Decimal("100.00")
        h2.monto_exigido = Decimal("100.00")
        session.flush()

        summary = PaymentService.summary(session, order_id=order.id_pedido, principal=employee)
        assert summary["disponible_reportar"] == Decimal("200.00")
        assert summary["completamente_pagado"] is False

        receivable = PaymentService.cash_receivable_orders(session, employee)
        match = next((item for item in receivable if item["id_pedido"] == order.id_pedido), None)
        assert match is not None
        assert match["importe_disponible"] == Decimal("200.00")

    def test_pedido_200_con_transferencia_pendiente_100_disponibilidad_100(
        self, session, customer, employee
    ):
        """Pedido de C$200 con transferencia pendiente de C$100: disponibilidad máxima C$100."""
        order = create_order(session, customer)
        order.total_pedido = Decimal("200.00")
        h1 = session.get(HitoPago, (order.id_pedido, 1))
        h2 = session.get(HitoPago, (order.id_pedido, 2))
        h1.monto_exigido = Decimal("100.00")
        h2.monto_exigido = Decimal("100.00")
        session.flush()

        # Reportar transferencia de C$100 (anticipo)
        _transfer(session, order, customer, "100.00", scope="ANTICIPO")

        summary = PaymentService.summary(session, order_id=order.id_pedido, principal=employee)
        assert summary["total_pendiente_verificacion"] == Decimal("100.00")
        assert summary["disponible_reportar"] == Decimal("100.00")

        receivable = PaymentService.cash_receivable_orders(session, employee)
        match = next((item for item in receivable if item["id_pedido"] == order.id_pedido), None)
        assert match is not None
        assert match["importe_disponible"] == Decimal("100.00")

    def test_rechazo_cobro_efectivo_200_con_transferencia_pendiente_100(
        self, session, customer, employee
    ):
        """Intentar cobrar C$200 en efectivo mientras existe una transferencia pendiente de C$100: debe rechazarse."""
        order = create_order(session, customer)
        order.total_pedido = Decimal("200.00")
        h1 = session.get(HitoPago, (order.id_pedido, 1))
        h2 = session.get(HitoPago, (order.id_pedido, 2))
        h1.monto_exigido = Decimal("100.00")
        h2.monto_exigido = Decimal("100.00")
        session.flush()

        _transfer(session, order, customer, "100.00", scope="ANTICIPO")

        register = PaymentService().open_cash_register(
            session, opening_amount=Decimal("0"), principal=employee
        )

        with pytest.raises(Conflict, match="máximo disponible"):
            _cash(session, order, employee, "200.00", register, scope="TOTAL")

        PaymentService().close_cash_register(
            session, cash_register_id=register.id_caja,
            closing_amount=Decimal("0"), principal=employee
        )

    def test_pedido_200_con_pendiente_100_y_efectivo_100_impide_duplicacion(
        self, session, customer, employee
    ):
        """Pedido de C$200 con transferencia pendiente de C$100 y cobro en efectivo de C$100: debe impedirse cualquier duplicación."""
        order = create_order(session, customer)
        order.total_pedido = Decimal("200.00")
        h1 = session.get(HitoPago, (order.id_pedido, 1))
        h2 = session.get(HitoPago, (order.id_pedido, 2))
        h1.monto_exigido = Decimal("100.00")
        h2.monto_exigido = Decimal("100.00")
        session.flush()

        # Transferencia pendiente de C$100 (TOTAL)
        _transfer(session, order, customer, "100.00", scope="TOTAL")

        # Cobro en efectivo de los C$100 restantes (TOTAL)
        register = PaymentService().open_cash_register(
            session, opening_amount=Decimal("0"), principal=employee
        )
        _cash(session, order, employee, "100.00", register, scope="TOTAL")

        summary = PaymentService.summary(session, order_id=order.id_pedido, principal=employee)
        assert summary["total_verificado"] == Decimal("100.00")
        assert summary["total_pendiente_verificacion"] == Decimal("100.00")
        assert summary["disponible_reportar"] == Decimal("0.00")

        # Ya no debe aparecer en cash_receivable_orders
        receivable = PaymentService.cash_receivable_orders(session, employee)
        assert all(item["id_pedido"] != order.id_pedido for item in receivable)

        # Cualquier intento adicional de cobro debe ser rechazado
        with pytest.raises(Conflict, match="disponible"):
            _cash(session, order, employee, "1.00", register, scope="TOTAL")

        PaymentService().close_cash_register(
            session, cash_register_id=register.id_caja,
            closing_amount=Decimal("100.00"), principal=employee
        )

    def test_transferencia_verificada_100_permite_cobro_efectivo_saldo_100(
        self, session, customer, employee
    ):
        """Pedido con transferencia verificada de C$100 y saldo restante de C$100: debe permitir cobrar C$100 en efectivo."""
        order = create_order(session, customer)
        order.total_pedido = Decimal("200.00")
        h1 = session.get(HitoPago, (order.id_pedido, 1))
        h2 = session.get(HitoPago, (order.id_pedido, 2))
        h1.monto_exigido = Decimal("100.00")
        h2.monto_exigido = Decimal("100.00")
        session.flush()

        # Transferencia verificada de anticipo C$100
        t = _transfer(session, order, customer, "100.00", scope="ANTICIPO")
        PaymentService().confirm(session, payment_id=t.id_transaccion, principal=employee)

        # Selector debe mostrar C$100 disponibles
        receivable = PaymentService.cash_receivable_orders(session, employee)
        match = next((item for item in receivable if item["id_pedido"] == order.id_pedido), None)
        assert match is not None
        assert match["importe_disponible"] == Decimal("100.00")

        # Cobrar C$100 en efectivo
        register = PaymentService().open_cash_register(
            session, opening_amount=Decimal("0"), principal=employee
        )
        movement = _cash(session, order, employee, "100.00", register, scope="SALDO")
        assert movement.monto == Decimal("100.00")

        summary = PaymentService.summary(session, order_id=order.id_pedido, principal=employee)
        assert summary["total_verificado"] == Decimal("200.00")
        assert summary["completamente_pagado"] is True
        assert summary["disponible_reportar"] == Decimal("0.00")

        PaymentService().close_cash_register(
            session, cash_register_id=register.id_caja,
            closing_amount=Decimal("100.00"), principal=employee
        )

    def test_movimiento_caja_generacion_unica_e_idempotencia(
        self, session, customer, employee
    ):
        """
        Un cobro en efectivo exitoso genera:
        - Una sola transacción.
        - Un solo folio.
        - Un solo movimiento de caja.
        Y una solicitud duplicada con la misma clave idempotente no genera ingresos duplicados.
        """
        from app.models.entities import MovimientoCaja, RegistroAuditoria

        order = create_order(session, customer)
        register = PaymentService().open_cash_register(
            session, opening_amount=Decimal("0"), principal=employee
        )
        key = uuid4()

        # Primer cobro
        mov1 = PaymentService().register_cash_payment(
            session,
            order_id=order.id_pedido,
            cash_register_id=register.id_caja,
            amount=Decimal("45.00"),
            payment_scope="ANTICIPO",
            idempotency_key=key,
            principal=employee,
        )

        # Validaciones de unicidad de la primera llamada
        txs = list(
            session.scalars(
                select(Transaccion).where(
                    Transaccion.id_pedido == order.id_pedido,
                    Transaccion.metodo_pago == "EFECTIVO",
                )
            )
        )
        assert len(txs) == 1
        assert txs[0].monto_con_signo == Decimal("45.00")
        assert txs[0].estado_verificacion == "VERIFICADO"

        movs = list(
            session.scalars(
                select(MovimientoCaja).where(
                    MovimientoCaja.id_caja == register.id_caja,
                    MovimientoCaja.id_transaccion == txs[0].id_transaccion,
                )
            )
        )
        assert len(movs) == 1
        assert movs[0].folio_recibo == mov1.folio_recibo

        # Solicitud duplicada idéntica (misma clave idem)
        mov2 = PaymentService().register_cash_payment(
            session,
            order_id=order.id_pedido,
            cash_register_id=register.id_caja,
            amount=Decimal("45.00"),
            payment_scope="ANTICIPO",
            idempotency_key=key,
            principal=employee,
        )

        assert mov2.id_movimiento_caja == mov1.id_movimiento_caja
        assert mov2.folio_recibo == mov1.folio_recibo

        # Re-verificar que sigue existiendo un único movimiento y una única transacción
        txs_after = list(
            session.scalars(
                select(Transaccion).where(
                    Transaccion.id_pedido == order.id_pedido,
                    Transaccion.metodo_pago == "EFECTIVO",
                )
            )
        )
        assert len(txs_after) == 1

        movs_after = list(
            session.scalars(
                select(MovimientoCaja).where(
                    MovimientoCaja.id_caja == register.id_caja,
                )
            )
        )
        assert len(movs_after) == 1

        PaymentService().close_cash_register(
            session, cash_register_id=register.id_caja,
            closing_amount=Decimal("50.00"), principal=employee
        )


# ---------------------------------------------------------------------------
# BUG 4 — Contrato de API: el detalle del pedido expone puede_cancelar y el
#          formulario de cancelación funciona (verificación del endpoint)
# ---------------------------------------------------------------------------


class TestDetalleOrdenApiContrato:
    """
    Bug 4: La corrección es en frontend (bindOrderDetails en showOrderDetail).
    Aquí se verifica que el backend retorna el contrato correcto para que
    el frontend pueda renderizar y activar el formulario.
    """

    def test_detail_endpoint_expone_puede_cancelar_true_para_pedido_limpio(
        self, api_client_factory, customer
    ):
        """GET /portal/pedidos/{code} debe devolver puede_cancelar=true si no hay pagos."""
        client = api_client_factory(customer)
        # Crear pedido
        resp = client.post(
            "/api/v1/portal/pedidos",
            json={"lines": [{"variant_id": 1, "quantity": 1}], "delivery_mode": "RETIRO"},
        )
        assert resp.status_code == 201
        code = resp.json()["codigo"]

        detail = client.get(f"/api/v1/portal/pedidos/{code}")
        assert detail.status_code == 200
        data = detail.json()
        assert data["puede_cancelar"] is True
        assert data["motivo_bloqueo_cancelacion"] is None

    def test_detail_endpoint_expone_puede_cancelar_false_tras_rechazo_incompleto(
        self, api_client_factory, customer, employee, session
    ):
        """
        Después de rechazar una transferencia, puede_cancelar debe ser True,
        no False. Verificación del contrato corregido.
        """
        client_c = api_client_factory(customer)
        client_e = api_client_factory(employee)

        # Crear pedido y obtener código
        resp = client_c.post(
            "/api/v1/portal/pedidos",
            json={"lines": [{"variant_id": 1, "quantity": 1}], "delivery_mode": "RETIRO"},
        )
        assert resp.status_code == 201
        code = resp.json()["codigo"]
        order_id = resp.json()["id_pedido"] if "id_pedido" in resp.json() else None

        # Reportar transferencia
        pay_resp = client_c.post(
            f"/api/v1/portal/pedidos/{code}/pagos",
            json={
                "idempotency_key": str(uuid4()),
                "amount": "10.00",
                "payment_scope": "TOTAL",
                "method": "TRANSFERENCIA",
                "bank_origin": "BANCO PRUEBA",
                "bank_receiver": None,
                "reference": f"REF-FIX-{uuid4().hex[:8]}",
            },
        )
        assert pay_resp.status_code == 201
        txn_id = pay_resp.json()["id_transaccion"]

        # Rechazar la transferencia
        rej = client_e.post(
            f"/api/v1/pagos/{txn_id}/rechazar",
            json={"reason": "No localizado en estado de cuenta"},
        )
        assert rej.status_code == 200
        assert rej.json()["estado_verificacion"] == "RECHAZADO"

        # Verificar que el detalle del portal ahora permite cancelar
        detail = client_c.get(f"/api/v1/portal/pedidos/{code}")
        assert detail.status_code == 200
        data = detail.json()
        assert data["puede_cancelar"] is True, (
            f"Tras rechazar la única transferencia, puede_cancelar debe ser True. "
            f"motivo_bloqueo: {data.get('motivo_bloqueo_cancelacion')}"
        )

    def test_cancel_endpoint_funciona_tras_rechazo(self, api_client_factory, customer, employee):
        """
        POST /portal/pedidos/{code}/cancelar debe aceptar la cancelación
        después de que la única transferencia fue rechazada.
        """
        client_c = api_client_factory(customer)
        client_e = api_client_factory(employee)

        resp = client_c.post(
            "/api/v1/portal/pedidos",
            json={"lines": [{"variant_id": 1, "quantity": 1}], "delivery_mode": "RETIRO"},
        )
        assert resp.status_code == 201
        code = resp.json()["codigo"]

        pay_resp = client_c.post(
            f"/api/v1/portal/pedidos/{code}/pagos",
            json={
                "idempotency_key": str(uuid4()),
                "amount": "10.00",
                "payment_scope": "TOTAL",
                "method": "TRANSFERENCIA",
                "bank_origin": "BANCO PRUEBA",
                "bank_receiver": None,
                "reference": f"REF-CANCEL-{uuid4().hex[:8]}",
            },
        )
        txn_id = pay_resp.json()["id_transaccion"]
        client_e.post(
            f"/api/v1/pagos/{txn_id}/rechazar",
            json={"reason": "Rechazo de prueba"},
        )

        cancel = client_c.post(
            f"/api/v1/portal/pedidos/{code}/cancelar",
            json={"reason": "Cancelación tras rechazo de transferencia"},
        )
        assert cancel.status_code == 200, (
            f"Se esperaba 200 pero se obtuvo {cancel.status_code}: {cancel.text}"
        )
        assert cancel.json()["estado"] == "CANCELADO"

