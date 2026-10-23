import os
import sqlite3
import datetime

class DIYPriceTracker:
    def __init__(self, db_path="data/price_history.db"):
        """Initializes SQLite database for multi-platform price tracking."""
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._create_tables()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _create_tables(self):
        """Creates tables for unique products and timestamped price logs."""
        with self._get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE,
                    title TEXT,
                    platform TEXT,
                    lowest_price REAL,
                    highest_price REAL
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS price_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT,
                    price REAL,
                    mrp REAL,
                    timestamp TEXT
                )
            ''')

    def track_and_evaluate(self, url: str, title: str, platform: str, price: float, mrp: float) -> dict:
        """
        Logs current price, compares with historical records, 
        and returns intelligence metrics (lowest ever, average price).
        """
        timestamp = datetime.datetime.now().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Check if product already exists in database
            cursor.execute("SELECT lowest_price, highest_price FROM products WHERE url = ?", (url,))
            row = cursor.fetchone()

            is_lowest_ever = False

            if row:
                lowest_ever, highest_ever = row
                if price < lowest_ever:
                    lowest_ever = price
                    is_lowest_ever = True
                if mrp > highest_ever:
                    highest_ever = mrp
                
                # Update aggregate product record
                conn.execute(
                    "UPDATE products SET title = ?, lowest_price = ?, highest_price = ? WHERE url = ?",
                    (title, lowest_ever, highest_ever, url)
                )
            else:
                lowest_ever = price
                highest_ever = mrp if mrp > price else price
                is_lowest_ever = True
                
                # Insert new product record
                conn.execute(
                    "INSERT INTO products (url, title, platform, lowest_price, highest_price) VALUES (?, ?, ?, ?, ?)",
                    (url, title, platform, lowest_ever, highest_ever)
                )

            # 2. Log this specific price point in time-series history
            conn.execute(
                "INSERT INTO price_logs (url, price, mrp, timestamp) VALUES (?, ?, ?, ?)",
                (url, price, mrp, timestamp)
            )

            # 3. Calculate historical average price for this URL
            cursor.execute("SELECT AVG(price) FROM price_logs WHERE url = ?", (url,))
            avg_row = cursor.fetchone()
            historical_avg = avg_row[0] if avg_row and avg_row[0] else price

            return {
                "is_lowest_ever": is_lowest_ever,
                "lowest_ever": lowest_ever,
                "highest_ever": highest_ever,
                "historical_avg": round(historical_avg, 2)
            }
