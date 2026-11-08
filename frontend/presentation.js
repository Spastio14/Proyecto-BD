(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.UiPresentation = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  const labels = {
    PENDIENTE_PAGO: "Pendiente de pago",
    PAGADO_PARCIAL: "Pago parcial recibido",
    PAGADO: "Pago confirmado",
    EN_DISENO: "En diseño",
    EN_PRODUCCION: "En producción",
    LISTO: "Listo para entregar",
    ENTREGADO: "Entregado",
    CANCELADO: "Cancelado",
    EXPIRADO: "Expirado",
    RECHAZADO: "Rechazado",
    PENDIENTE: "Pendiente de revisión",
    VERIFICADO: "Verificado",
    EMITIDA: "Pendiente de respuesta",
    ACEPTADA: "Aceptada",
    RECHAZADA: "Rechazada",
    CONVERTIDA: "Convertida en pedido",
    RETIRO: "Retiro en tienda",
    ENVIO: "Envío",
    PROGRAMADO: "Programado",
    EN_TRANSITO: "En tránsito",
    APROBADO: "Aprobado",
    DISPONIBLE: "Disponible",
    BAJO_PEDIDO: "Disponible por encargo",
    ACTIVA: "Activa",
    INACTIVA: "Inactiva",
    ACTIVO: "Activo",
    INACTIVO: "Inactivo",
    BORRADOR: "Borrador",
    PUBLICADO: "Publicado",
    SALIDA_PRODUCCION: "Consumo de producción",
    SALIDA_PERDIDA: "Pérdida registrada",
    ENTRADA_COMPRA: "Entrada por compra",
    AJUSTE_ENTRADA: "Ajuste de entrada",
    AJUSTE_SALIDA: "Ajuste de salida",
    ANTICIPO: "Anticipo",
    SALDO: "Saldo",
    TRANSFERENCIA: "Transferencia",
    EFECTIVO: "Efectivo",
    TARJETA: "Tarjeta",
    OTRO: "Otro",
    REPORTAR_PAGO: "Reporta el pago para iniciar tu pedido",
    ESPERAR_DISENO: "Espera la preparación de tu diseño",
    ESPERAR_ACTUALIZACION: "Tu pago está siendo procesado",
    REVISAR_DISENO: "Revisa las novedades de tu diseño",
    ESPERAR_PRODUCCION: "Estamos produciendo tu pedido",
    ESPERAR_ENVIO: "Tu envío está siendo coordinado",
    COORDINAR_ENVIO: "Confirma los datos de entrega",
    RETIRAR_PEDIDO: "Tu pedido está listo para retirar",
    COMPLETADO: "Pedido completado",
    SIN_ACCION: "No se requiere ninguna acción",
    REPORTAR_ANTICIPO: "Registrar el anticipo",
    REPORTAR_SALDO: "Registrar el pago del saldo",
    INICIAR_DISENO: "Iniciar preparación del diseño",
    APROBAR_DISENOS: "Revisar y aprobar diseños",
    INICIAR_PRODUCCION: "Iniciar producción",
    CONSUMIR_RESERVAS: "Registrar consumo de materiales",
    COMPLETAR_PRODUCCION: "Completar producción",
    COMPLETAR_ENTREGA: "Completar entrega",
  };

  const orderMessages = {
    PENDIENTE_PAGO: "Pendiente de pago",
    PAGADO_PARCIAL: "Recibimos una parte de tu pago",
    PAGADO: "Tu pago fue confirmado",
    EN_DISENO: "Tu diseño está siendo preparado",
    EN_PRODUCCION: "Estamos produciendo tu pedido",
    LISTO: "Tu pedido está listo",
    ENTREGADO: "Tu pedido fue entregado",
    CANCELADO: "Este pedido fue cancelado",
    EXPIRADO: "Este pedido expiró",
  };

  function label(value) {
    if (value === null || value === undefined || value === "") return "—";
    const code = String(value);
    return labels[code] || code.toLowerCase().replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
  }

  function orderMessage(status) { return orderMessages[status] || label(status); }

  function orderProgressStages(order) {
    const reached = new Set((order.historial || []).map((item) => item.estado));
    reached.add(order.estado);
    const later = (states) => states.some((state) => reached.has(state));
    const stages = [
      { label:"Solicitud", completed:true, current:false },
      { label:"Pago", completed:later(["PAGADO_PARCIAL","PAGADO","EN_DISENO","EN_PRODUCCION","LISTO","ENTREGADO"]), current:order.estado === "PENDIENTE_PAGO" },
    ];
    if (order.requiere_produccion !== false) {
      stages.push(
        { label:"Diseño", completed:later(["EN_PRODUCCION","LISTO","ENTREGADO"]), current:order.estado === "EN_DISENO" },
        { label:"Producción", completed:later(["LISTO","ENTREGADO"]), current:order.estado === "EN_PRODUCCION" },
      );
    }
    stages.push(
      { label:"Listo", completed:reached.has("ENTREGADO"), current:order.estado === "LISTO" },
      { label:"Entregado", completed:order.estado === "ENTREGADO", current:order.estado === "ENTREGADO" },
    );
    return stages;
  }

  function money(value) {
    return new Intl.NumberFormat("es-NI", {
      style: "currency",
      currency: "NIO",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(Number(value || 0));
  }

  function date(value, withTime = false) {
    if (!value) return "—";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.valueOf())) return "—";
    return new Intl.DateTimeFormat("es-NI", {
      timeZone: "America/Managua",
      day: "numeric",
      month: "short",
      year: "numeric",
      ...(withTime ? { hour: "numeric", minute: "2-digit" } : {}),
    }).format(parsed);
  }

  function quantity(value, unit = "") {
    const amount = new Intl.NumberFormat("es-NI", { maximumFractionDigits: 3 }).format(Number(value || 0));
    const safeUnit = typeof unit === "string" ? unit.trim() : "";
    return safeUnit ? `${amount} ${label(safeUnit).toLowerCase()}` : amount;
  }

  function friendlyError(message, employee = false) {
    const source = String(message || "La operación no pudo completarse");
    if (/permiso\s+[A-Z][A-Z0-9_]+|falta el permiso/i.test(source)) {
      return employee
        ? "No tienes autorización para realizar esta operación. Solicita acceso al administrador si necesitas realizar esta tarea."
        : "No tienes autorización para realizar esta operación.";
    }
    return source;
  }

  return { labels, label, orderMessage, orderProgressStages, money, date, quantity, friendlyError };
});
