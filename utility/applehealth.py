from datetime import datetime


class HealthRecord:
    def __init__(self, record: dict):
        self.record_type = record.get("type").replace("HKQuantityTypeIdentifier", "")
        self.value = record.get("value")
        self.unit = record.get("unit")
        self.date = record.get("startDate")

    @property
    def date(self):
        return self._date
    @date.setter
    def date(self, value):
        # Convertit la date en format lisible
        self._date = datetime.strptime(value, "%Y-%m-%d %H:%M:%S %z") if value else None
        
    def __str__(self):
        return f"{self.record_type} - {self.value} {self.unit} on {self.date.date() if self.date else 'Unknown'}"

    def __repr__(self):
        return f"HealthRecord(type={self.record_type}, value={self.value}, date={self.date})"
