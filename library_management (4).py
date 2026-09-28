"""
Library Management System
Language : Python 3 (no extra libraries needed)
Database : SQLite (file: library.db, created automatically)

Features : Add/View/Search/Delete books, Register/View members,
           Issue book, Return book (with fine), Reports
"""

import sqlite3
from datetime import date, datetime

DB_NAME = "library.db"
LOAN_DAYS = 14        # days a book can be kept
FINE_PER_DAY = 2      # fine (Rs.) per late day


# ---------------------------------------------------------------- database
def connect():
    return sqlite3.connect(DB_NAME)


def setup_database():
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS books(
            book_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            title     TEXT NOT NULL,
            author    TEXT NOT NULL,
            category  TEXT,
            copies    INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS members(
            member_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name      TEXT NOT NULL,
            phone     TEXT,
            joined_on TEXT
        );
        CREATE TABLE IF NOT EXISTS issues(
            issue_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id     INTEGER NOT NULL,
            member_id   INTEGER NOT NULL,
            issue_date  TEXT NOT NULL,
            due_date    TEXT NOT NULL,
            return_date TEXT,
            fine        INTEGER DEFAULT 0,
            FOREIGN KEY(book_id)   REFERENCES books(book_id),
            FOREIGN KEY(member_id) REFERENCES members(member_id)
        );
        """)


# ---------------------------------------------------------------- helpers
def ask_int(prompt):
    while True:
        try:
            return int(input(prompt))
        except ValueError:
            print("  Please enter a number.")


def print_table(headers, rows):
    if not rows:
        print("  (no records found)")
        return
    widths = [max(len(str(h)), *(len(str(r[i])) for r in rows))
              for i, h in enumerate(headers)]
    line = "+-" + "-+-".join("-" * w for w in widths) + "-+"
    print(line)
    print("| " + " | ".join(str(h).ljust(w) for h, w in zip(headers, widths)) + " |")
    print(line)
    for r in rows:
        print("| " + " | ".join(str(v).ljust(w) for v, w in zip(r, widths)) + " |")
    print(line)


# ---------------------------------------------------------------- books
def add_book():
    title = input("Title    : ").strip()
    author = input("Author   : ").strip()
    category = input("Category : ").strip()
    copies = ask_int("Copies   : ")
    if not title or not author:
        print("  Title and author are required.")
        return
    with connect() as con:
        con.execute("INSERT INTO books(title,author,category,copies) VALUES(?,?,?,?)",
                    (title, author, category, copies))
    print("  Book added successfully.")


def view_books():
    with connect() as con:
        rows = con.execute("SELECT book_id,title,author,category,copies FROM books").fetchall()
    print_table(["ID", "Title", "Author", "Category", "Available"], rows)


def search_books():
    word = "%" + input("Search title/author/category: ").strip() + "%"
    with connect() as con:
        rows = con.execute(
            """SELECT book_id,title,author,category,copies FROM books
               WHERE title LIKE ? OR author LIKE ? OR category LIKE ?""",
            (word, word, word)).fetchall()
    print_table(["ID", "Title", "Author", "Category", "Available"], rows)


def delete_book():
    book_id = ask_int("Book ID to delete: ")
    with connect() as con:
        pending = con.execute(
            "SELECT COUNT(*) FROM issues WHERE book_id=? AND return_date IS NULL",
            (book_id,)).fetchone()[0]
        if pending:
            print("  Cannot delete: this book is currently issued.")
            return
        cur = con.execute("DELETE FROM books WHERE book_id=?", (book_id,))
    print("  Book deleted." if cur.rowcount else "  Book ID not found.")


# ---------------------------------------------------------------- members
def add_member():
    name = input("Name  : ").strip()
    phone = input("Phone : ").strip()
    if not name:
        print("  Name is required.")
        return
    with connect() as con:
        cur = con.execute("INSERT INTO members(name,phone,joined_on) VALUES(?,?,?)",
                          (name, phone, str(date.today())))
    print(f"  Member registered. Member ID = {cur.lastrowid}")


def view_members():
    with connect() as con:
        rows = con.execute("SELECT member_id,name,phone,joined_on FROM members").fetchall()
    print_table(["ID", "Name", "Phone", "Joined On"], rows)


# ---------------------------------------------------------------- issue / return
def issue_book():
    book_id = ask_int("Book ID   : ")
    member_id = ask_int("Member ID : ")
    with connect() as con:
        book = con.execute("SELECT title,copies FROM books WHERE book_id=?", (book_id,)).fetchone()
        member = con.execute("SELECT name FROM members WHERE member_id=?", (member_id,)).fetchone()
        if not book:
            print("  Book not found.")
            return
        if not member:
            print("  Member not found.")
            return
        if book[1] <= 0:
            print("  Sorry, no copies available.")
            return
        issued = date.today()
        due = date.fromordinal(issued.toordinal() + LOAN_DAYS)
        con.execute("INSERT INTO issues(book_id,member_id,issue_date,due_date) VALUES(?,?,?,?)",
                    (book_id, member_id, str(issued), str(due)))
        con.execute("UPDATE books SET copies=copies-1 WHERE book_id=?", (book_id,))
    print(f"  '{book[0]}' issued to {member[0]}. Due date: {due}")


def return_book():
    issue_id = ask_int("Issue ID: ")
    with connect() as con:
        row = con.execute(
            "SELECT book_id,due_date FROM issues WHERE issue_id=? AND return_date IS NULL",
            (issue_id,)).fetchone()
        if not row:
            print("  No active issue found with that ID.")
            return
        book_id, due = row
        today = date.today()
        late_days = (today - datetime.strptime(due, "%Y-%m-%d").date()).days
        fine = max(0, late_days) * FINE_PER_DAY
        con.execute("UPDATE issues SET return_date=?, fine=? WHERE issue_id=?",
                    (str(today), fine, issue_id))
        con.execute("UPDATE books SET copies=copies+1 WHERE book_id=?", (book_id,))
    print("  Book returned.", f"Late by {late_days} day(s). Fine = Rs.{fine}" if fine else "No fine.")


# ---------------------------------------------------------------- reports
def report_issued():
    with connect() as con:
        rows = con.execute(
            """SELECT i.issue_id,b.title,m.name,i.issue_date,i.due_date
               FROM issues i JOIN books b ON b.book_id=i.book_id
                             JOIN members m ON m.member_id=i.member_id
               WHERE i.return_date IS NULL""").fetchall()
    print_table(["Issue ID", "Book", "Member", "Issued", "Due"], rows)


def report_overdue():
    with connect() as con:
        rows = con.execute(
            """SELECT i.issue_id,b.title,m.name,i.due_date
               FROM issues i JOIN books b ON b.book_id=i.book_id
                             JOIN members m ON m.member_id=i.member_id
               WHERE i.return_date IS NULL AND i.due_date < ?""",
            (str(date.today()),)).fetchall()
    print_table(["Issue ID", "Book", "Member", "Due Date"], rows)


def report_history():
    with connect() as con:
        rows = con.execute(
            """SELECT i.issue_id,b.title,m.name,i.issue_date,
                      IFNULL(i.return_date,'-'),i.fine
               FROM issues i JOIN books b ON b.book_id=i.book_id
                             JOIN members m ON m.member_id=i.member_id
               ORDER BY i.issue_id DESC""").fetchall()
    print_table(["Issue ID", "Book", "Member", "Issued", "Returned", "Fine"], rows)


# ---------------------------------------------------------------- menu
MENU = """
========== LIBRARY MANAGEMENT SYSTEM ==========
 1. Add book              7. Issue book
 2. View all books        8. Return book
 3. Search books          9. Issued books report
 4. Delete book          10. Overdue books report
 5. Register member      11. Full issue history
 6. View members          0. Exit
================================================"""

ACTIONS = {
    1: add_book, 2: view_books, 3: search_books, 4: delete_book,
    5: add_member, 6: view_members, 7: issue_book, 8: return_book,
    9: report_issued, 10: report_overdue, 11: report_history,
}


def main():
    setup_database()
    while True:
        print(MENU)
        choice = ask_int("Enter choice: ")
        if choice == 0:
            print("Thank you. Goodbye!")
            break
        action = ACTIONS.get(choice)
        if action:
            print()
            action()
        else:
            print("  Invalid choice, try again.")


if __name__ == "__main__":
    main()
