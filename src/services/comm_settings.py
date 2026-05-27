# src/services/comm_settings.py
class CommSettings:
    """兼容外壳：内部转发到 CommunicationService。"""

    def __init__(self, service=None):
        from src.application.services import CommunicationService

        self.service = service or CommunicationService()
        self.settings = self.service.settings
        self.default_settings = self.service.default_settings

    def load_settings(self):
        self.settings = self.service.reload()
        return self.settings

    def save_settings(self) -> None:
        self.service.save()

    def get_mfc_config(self):
        return self.service.get_mfc_config()

    def get_temp_config(self):
        return self.service.get_temp_config()

    def get_balance_config(self):
        return self.service.get_balance_config()

    def get_sampling_config(self):
        return self.service.get_sampling_config()

    def get_mfc_slave_addresses(self):
        return self.service.get_mfc_slave_addresses()

    def get_flow_scaling(self):
        return self.service.get_flow_scaling()

    def get_temp_channels(self):
        return self.service.get_temp_channels()

    @staticmethod
    def get_available_ports():
        from src.infrastructure.repositories import SerialPortDiscovery

        return SerialPortDiscovery().list_ports()
