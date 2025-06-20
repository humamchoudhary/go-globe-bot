from datetime import datetime, UTC
from pymongo import MongoClient


class UsageService:
    def __init__(self, db):
        self.db = db
        self.collection = db.usage

    def get_cost(self):
        """Retrieves all token usage data as a structured dictionary."""
        usage_data = {}
        for doc in self.collection.find():
            period = doc["period"]
            date = doc["date"]
            if period not in usage_data:
                usage_data[period] = {}
            usage_data[period][date] = {
                "cost": doc.get("cost", []),
                "input_tokens": doc.get("input_tokens", []),
                "output_tokens": doc.get("output_tokens", []),
            }
        return usage_data

    def add_cost(self, input_tokens, output_tokens, cost):
        """Logs token usage into daily (hourly), weekly/monthly (daily), and yearly (monthly) records."""
        now = datetime.now(UTC)  # Fix for deprecation warning

        hour_index = now.hour
        day_index = now.day - 1  # 0-based index
        # week_index = now.isocalendar()[1] - 1  # 0-based index for weeks
        month_index = now.month - 1  # 0-based index for months

        periods = {
            "daily": (now.strftime("%Y-%m-%d"), 24, hour_index),
            # Monday=0, Sunday=6
            # "weekly": (f"{now.year}-W{now.isocalendar()[1]}", 7, now.weekday()),
            # Max days in month
            "monthly": (now.strftime("%Y-%m"), 31, day_index),
            "yearly": (now.strftime("%Y"), 12, month_index),
        }

        for period, (date_key, size, index) in periods.items():
            query = {"period": period, "date": date_key}

            # Ensure array exists and has the correct size
            existing_doc = self.collection.find_one(query)
            if not existing_doc:
                self.collection.insert_one(
                    {
                        "period": period,
                        "date": date_key,
                        "cost": [0] * size,
                        "input_tokens": [0] * size,
                        "output_tokens": [0] * size,
                    }
                )

            # Increment specific index
            self.collection.update_one(
                query,
                {
                    "$inc": {
                        f"cost.{index}": cost,
                        f"input_tokens.{index}": input_tokens,
                        f"output_tokens.{index}": output_tokens,
                    }
                },
            )


def log_usage(input_tokens: int, output_tokens: int, cost: float):
    """Logs token usage into daily (hourly), weekly/monthly (daily), and yearly (monthly) records."""
    now = datetime.now(UTC)  # Fix for deprecation warning

    hour_index = now.hour
    day_index = now.day - 1  # 0-based index
    week_index = now.isocalendar()[1] - 1  # 0-based index for weeks
    month_index = now.month - 1  # 0-based index for months

    periods = {
        "daily": (now.strftime("%Y-%m-%d"), 24, hour_index),
        # Monday=0, Sunday=6
        # "weekly": (f"{now.year}-W{now.isocalendar()[1]}", 7, now.weekday()),
        "monthly": (now.strftime("%Y-%m"), 31, day_index),  # Max days in month
        "yearly": (now.strftime("%Y"), 12, month_index),
    }

    for period, (date_key, size, index) in periods.items():
        query = {"period": period, "date": date_key}

        # Ensure array exists and has the correct size
        existing_doc = collection.find_one(query)
        if not existing_doc:
            collection.insert_one(
                {
                    "period": period,
                    "date": date_key,
                    "cost": [0] * size,
                    "input_tokens": [0] * size,
                    "output_tokens": [0] * size,
                }
            )

        # Increment specific index
        collection.update_one(
            query,
            {
                "$inc": {
                    f"cost.{index}": cost,
                    f"input_tokens.{index}": input_tokens,
                    f"output_tokens.{index}": output_tokens,
                }
            },
        )


def get_usage():
    """Retrieves all token usage data as a structured dictionary."""
    usage_data = {}
    for doc in collection.find():
        period = doc["period"]
        date = doc["date"]
        if period not in usage_data:
            usage_data[period] = {}
        usage_data[period][date] = {
            "cost": doc.get("cost", []),
            "input_tokens": doc.get("input_tokens", []),
            "output_tokens": doc.get("output_tokens", []),
        }
    return usage_data


if __name__ == "__main__":
    client = MongoClient("mongodb://localhost:27017/")
    db = client["test"]
    collection = db["usage"]
    log_usage(100, 10, 400)
    # print(get_usage())
