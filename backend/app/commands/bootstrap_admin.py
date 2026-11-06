import argparse

from app.core.config import get_settings
from app.db.session import build_engine, build_session_factory
from app.integrations.supabase import SupabaseHTTPClient
from app.services.employees import EmployeeInvitationCoordinator


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description="Inicializa una identidad Supabase verificada como primer administrador"
    )
    command.add_argument("--auth-user-id", required=True)
    command.add_argument("--names", required=True)
    command.add_argument("--surnames")
    command.add_argument("--phone")
    command.add_argument("--document")
    command.add_argument("--employee-code", required=True)
    command.add_argument(
        "--confirm",
        action="store_true",
        help="Confirma que el propietario autorizó esta inicialización de una sola vez",
    )
    return command


def main() -> None:
    args = parser().parse_args()
    if not args.confirm:
        raise SystemExit("Falta --confirm; no se realizó ninguna operación")
    settings = get_settings()
    if not (
        settings.supabase_url
        and settings.supabase_public_key
        and settings.supabase_secret_key
    ):
        raise SystemExit("Supabase Auth administrativo no está configurado")
    gateway = SupabaseHTTPClient(
        settings.supabase_url,
        settings.supabase_public_key.get_secret_value(),
        settings.supabase_secret_key.get_secret_value(),
    )
    identity = gateway.get_user(subject=args.auth_user_id)
    engine = build_engine(settings)
    try:
        coordinator = EmployeeInvitationCoordinator(
            build_session_factory(engine),
            gateway,
            redirect_to=settings.employee_invite_redirect_url,
        )
        result = coordinator.bootstrap_admin(
            identity=identity,
            names=args.names,
            surnames=args.surnames,
            phone=args.phone,
            document=args.document,
            employee_code=args.employee_code,
        )
    finally:
        engine.dispose()
    print(
        f"Administrador preparado: persona={result.persona_id} "
        f"codigo={result.employee_code} estado={result.status}"
    )


if __name__ == "__main__":
    main()
