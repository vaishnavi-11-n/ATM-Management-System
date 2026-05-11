import tkinter as tk
from tkinter import messagebox
import hashlib
import mysql.connector
from mysql.connector import Error
from datetime import datetime


# ------------ DATABASE BACKEND ------------

class ATMBackend:
    def __init__(self,
                 db_user="root",
                 db_password="your_mysql_password",
                 db_host="localhost",
                 db_name="atm_db",
                 account_id=1):
        """
        account_id: which row in atm_accounts this GUI will operate on.
        """
        self.account_id = account_id

        try:
            self.conn = mysql.connector.connect(
                user=db_user,
                password=db_password,
                host=db_host,
                database=db_name
            )
            self.cursor = self.conn.cursor(dictionary=True)
        except Error as e:
            messagebox.showerror("DB Error", f"Cannot connect to database:\n{e}")
            raise

        # verify that account exists
        self.cursor.execute(
            "SELECT id, pin_hash, balance FROM atm_accounts WHERE id = %s",
            (self.account_id,)
        )
        row = self.cursor.fetchone()
        if not row:
            messagebox.showerror("DB Error", f"Account id {self.account_id} not found")
            raise SystemExit

        self.pin_hash = row["pin_hash"]

    # ---- helpers ----
    def hash_pin(self, pin_str):
        return hashlib.sha256(pin_str.encode()).hexdigest()

    def check_pin(self, pin):
        return self.pin_hash == self.hash_pin(str(pin))

    def _get_balance_db(self):
        self.cursor.execute(
            "SELECT balance FROM atm_accounts WHERE id = %s",
            (self.account_id,)
        )
        row = self.cursor.fetchone()
        return int(row["balance"])

    def _update_balance_db(self, new_balance):
        self.cursor.execute(
            "UPDATE atm_accounts SET balance = %s WHERE id = %s",
            (new_balance, self.account_id)
        )
        self.conn.commit()

    def _insert_history(self, t_type, amount, old_bal, new_bal):
        self.cursor.execute(
            """
            INSERT INTO atm_history
                (account_id, transaction_type, amount,
                 old_balance, new_balance, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (self.account_id, t_type, amount, old_bal,
             new_bal, datetime.now())
        )
        self.conn.commit()

    # ---- public operations ----
    def withdraw(self, amount):
        old_bal = self._get_balance_db()
        if amount > old_bal:
            return False, "Not enough balance"
        new_bal = old_bal - amount
        self._update_balance_db(new_bal)
        self._insert_history("withdraw", amount, old_bal, new_bal)
        return True, new_bal

    def deposit(self, amount):
        old_bal = self._get_balance_db()
        new_bal = old_bal + amount
        self._update_balance_db(new_bal)
        self._insert_history("deposit", amount, old_bal, new_bal)
        return new_bal

    def change_pin(self, old, new):
        if not self.check_pin(old):
            return False, "Wrong current PIN"
        new_hash = self.hash_pin(str(new))
        self.cursor.execute(
            "UPDATE atm_accounts SET pin_hash = %s WHERE id = %s",
            (new_hash, self.account_id)
        )
        self.conn.commit()
        self.pin_hash = new_hash
        self._insert_history("change_pin", 0, self._get_balance_db(),
                             self._get_balance_db())
        return True, "PIN changed!"

    def get_balance(self):
        return self._get_balance_db()

    def close(self):
        try:
            self.cursor.close()
            self.conn.close()
        except Exception:
            pass


# ------------ TKINTER GUI ------------

class ATM:
    def __init__(self, root):
        # change db_name/account_id as needed
        self.backend = ATMBackend(
            db_user="root",
            db_password="your_password",
            db_host="localhost",
            db_name="atm_db",
            account_id=1
        )

        self.root = root
        self.root.title("ATM")
        self.root.geometry("350x360")
        self.menu = tk.Frame(root, bg='light blue')
        self.menu.place(x=25, y=25, width=300, height=300)
        self.account_type()

        # close DB when window closes
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        self.backend.close()
        self.root.destroy()

    def clear(self):
        for w in self.menu.winfo_children():
            w.destroy()

    def account_type(self):
        self.clear()
        tk.Label(self.menu, text="Select Account",
                 bg='light blue', font=('', 12)).pack(pady=10)
        var = tk.IntVar(value=1)
        tk.Radiobutton(self.menu, text="Savings",
                       variable=var, value=1,
                       bg='light blue').pack()
        tk.Radiobutton(self.menu, text="Current",
                       variable=var, value=2,
                       bg='light blue').pack()

        def ok():
            if var.get() == 1:
                self.main_menu()
            else:
                self.clear()
                tk.Label(self.menu, text="Current account not available.",
                         bg='light blue').pack(pady=10)
                tk.Button(self.menu, text="Back",
                          command=self.account_type).pack()

        tk.Button(self.menu, text="OK", command=ok).pack(pady=10)

    def main_menu(self):
        self.clear()
        tk.Label(self.menu, text="ATM Menu", bg='light blue',
                 font=('', 12, 'bold')).pack(pady=10)
        tk.Button(self.menu, text="Withdraw",
                  command=self.withdraw).pack(pady=3, fill="x")
        tk.Button(self.menu, text="Deposit",
                  command=self.deposit).pack(pady=3, fill="x")
        tk.Button(self.menu, text="Balance",
                  command=self.balance).pack(pady=3, fill="x")
        tk.Button(self.menu, text="Change PIN",
                  command=self.change_pin).pack(pady=3, fill="x")
        tk.Button(self.menu, text="Exit",
                  command=self.on_close).pack(pady=10, fill="x")

    def withdraw(self):
        self.form_window("Withdraw", self._withdraw_action)

    def deposit(self):
        self.form_window("Deposit", self._deposit_action)

    def balance(self):
        self.simple_pin_window("Check Balance", self._balance_action)

    def change_pin(self):
        self.change_pin_window()

    def form_window(self, action, callback):
        self.clear()
        tk.Label(self.menu, text=action, bg='light blue').pack(pady=10)
        tk.Label(self.menu, text="PIN", bg='light blue').pack()
        pin = tk.Entry(self.menu, show='*')
        pin.pack()
        tk.Label(self.menu, text="Amount", bg='light blue').pack()
        amt = tk.Entry(self.menu)
        amt.pack()

        def submit():
            callback(pin.get(), amt.get())

        tk.Button(self.menu, text="Submit",
                  command=submit).pack(pady=8)
        tk.Button(self.menu, text="Back",
                  command=self.main_menu).pack()

    def simple_pin_window(self, action, callback):
        self.clear()
        tk.Label(self.menu, text=action, bg='light blue').pack(pady=10)
        tk.Label(self.menu, text="PIN", bg='light blue').pack()
        pin = tk.Entry(self.menu, show='*')
        pin.pack()

        def submit():
            callback(pin.get())

        tk.Button(self.menu, text="Submit",
                  command=submit).pack(pady=8)
        tk.Button(self.menu, text="Back",
                  command=self.main_menu).pack()

    def change_pin_window(self):
        self.clear()
        tk.Label(self.menu, text="Change PIN",
                 bg='light blue').pack(pady=10)
        tk.Label(self.menu, text="Current PIN",
                 bg='light blue').pack()
        op = tk.Entry(self.menu, show='*')
        op.pack()
        tk.Label(self.menu, text="New PIN",
                 bg='light blue').pack()
        np = tk.Entry(self.menu, show='*')
        np.pack()
        tk.Label(self.menu, text="Confirm New PIN",
                 bg='light blue').pack()
        cp = tk.Entry(self.menu, show='*')
        cp.pack()

        def submit():
            old = op.get()
            new = np.get()
            conf = cp.get()
            if not (old.isdigit() and new.isdigit() and conf.isdigit()):
                messagebox.showerror("Error", "PINs must be numbers")
                return
            if new != conf:
                messagebox.showerror("Error", "New PINs don't match")
                return
            ok, msg = self.backend.change_pin(int(old), int(new))
            if ok:
                messagebox.showinfo("Success", msg)
                self.main_menu()
            else:
                messagebox.showerror("Error", msg)

        tk.Button(self.menu, text="Submit",
                  command=submit).pack(pady=8)
        tk.Button(self.menu, text="Back",
                  command=self.main_menu).pack()

    def _withdraw_action(self, pin, amt):
        if not (pin.isdigit() and amt.isdigit()):
            messagebox.showerror("Error", "Enter valid numbers")
            return
        if not self.backend.check_pin(int(pin)):
            messagebox.showerror("Error", "Wrong PIN")
            return
        ok, res = self.backend.withdraw(int(amt))
        if ok:
            messagebox.showinfo("Withdraw",
                                f"Taken: {amt}\nBalance: {res}")
            self.main_menu()
        else:
            messagebox.showerror("Error", res)

    def _deposit_action(self, pin, amt):
        if not (pin.isdigit() and amt.isdigit()):
            messagebox.showerror("Error", "Enter valid numbers")
            return
        if not self.backend.check_pin(int(pin)):
            messagebox.showerror("Error", "Wrong PIN")
            return
        bal = self.backend.deposit(int(amt))
        messagebox.showinfo("Deposit",
                            f"Added: {amt}\nBalance: {bal}")
        self.main_menu()

    def _balance_action(self, pin):
        if not pin.isdigit():
            messagebox.showerror("Error", "PIN must be number")
            return
        if not self.backend.check_pin(int(pin)):
            messagebox.showerror("Error", "Wrong PIN")
            return
        bal = self.backend.get_balance()
        messagebox.showinfo("Balance", f"Your Balance: {bal}")
        self.main_menu()


if __name__ == "__main__":
    root = tk.Tk()
    ATM(root)
    root.mainloop()
