import sqlite3

class DatabaseManager:
    def __init__(self, db_name="deals_history.db"):
        self.conn = sqlite3.connect(db_name)
        self.create_tables()

    def create_tables(self):
        query = """
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT UNIQUE,
            title TEXT,
            lowest_price REAL,
            last_posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        self.conn.execute(query)
        self.conn.commit()

    def is_lowest_price(self, product_id: str, current_price: float) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT lowest_price FROM price_history WHERE product_id = ?", (product_id,))
        row = cursor.fetchone()

        if row is None:
            cursor.execute("INSERT INTO price_history (product_id, lowest_price) VALUES (?, ?)", (product_id, current_price))
            self.conn.commit()
            return True
        elif current_price < row[0]:
            cursor.execute("UPDATE price_history SET lowest_price = ? WHERE product_id = ?", (current_price, product_id))
            self.conn.commit()
            return True
        return False
