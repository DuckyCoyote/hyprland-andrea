"""Registro de fuentes de estado. Para añadir un dominio nuevo: crea un módulo con una
subclase de daemon.Source y añádela a esta lista (ver docs/widgets.md)."""


def all_sources():
    from .apps import AppsSource
    from .appearance import AppearanceSource
    from .audio import AudioSource
    from .media import MediaSource
    from .network import NetworkSource
    from .notifications import NotificationsSource
    from .popup import PopupSource
    from .system import SystemSource
    from .updates import UpdatesSource
    from .weather import WeatherSource
    from .wm import WmSource

    # wm primero: el resto (popups, energía) depende del adaptador del compositor
    return [WmSource, PopupSource, AppearanceSource, AudioSource, NetworkSource, MediaSource,
            UpdatesSource, WeatherSource, SystemSource, AppsSource, NotificationsSource]
