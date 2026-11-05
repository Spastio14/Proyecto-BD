ACTIVE_GUEST_STATES = frozenset(
    {"PENDIENTE_PAGO", "PAGADO_PARCIAL", "PAGADO", "EN_DISENO", "EN_PRODUCCION", "LISTO"}
)

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "PENDIENTE_PAGO": frozenset({"PAGADO_PARCIAL", "PAGADO", "CANCELADO", "EXPIRADO"}),
    "PAGADO_PARCIAL": frozenset({"PAGADO", "EN_DISENO", "CANCELADO"}),
    "PAGADO": frozenset({"EN_DISENO", "CANCELADO"}),
    "EN_DISENO": frozenset({"EN_PRODUCCION", "CANCELADO"}),
    "EN_PRODUCCION": frozenset({"LISTO", "CANCELADO"}),
    "LISTO": frozenset({"ENTREGADO", "CANCELADO"}),
    "ENTREGADO": frozenset(),
    "CANCELADO": frozenset(),
    "EXPIRADO": frozenset(),
}
