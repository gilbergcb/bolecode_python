"""SignalHub — ponte thread-safe entre backend (APScheduler) e UI (PySide6)."""

from PySide6.QtCore import QObject, Signal


class SignalHub(QObject):
    """Singleton de sinais. Emitidos de qualquer thread, recebidos na UI thread."""

    # Dados atualizados (refresh periódico)
    kpis_updated = Signal(dict)
    boletos_updated = Signal(dict)
    logs_updated = Signal(list)
    scheduler_updated = Signal(dict)

    # Eventos de jobs (emitidos do callback do scheduler)
    job_completed = Signal(str, str, int)  # (job_name, status, count)

    # Notificações toast
    boleto_registered = Signal(str, str)   # (numtransvenda, prest)
    payment_received = Signal(str, float)  # (nosso_numero, valor)
    error_occurred = Signal(str, str)      # (context, message)

    # Status do serviço
    service_status_changed = Signal(bool)  # True=ok, False=erro
