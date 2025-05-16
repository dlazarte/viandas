import reflex as rx
import datetime
import mysql.connector

# Database configuration (replace with your actual credentials)
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '12345',
    'database': 'your_database_name',  # Replace with your database name
}

class State(rx.State):
    date: str = datetime.date.today().strftime("%Y-%m-%d") # Initialize with today's date
    procedure_result: str = ""
    error_message: str = ""

    def call_procedure(self):
        try:
            connection = mysql.connector.connect(**DB_CONFIG)
            cursor = connection.cursor()

            # Call the stored procedure (replace with your procedure name)
            procedure_name = "your_stored_procedure_name" #Replace this line
            cursor.callproc(procedure_name, [self.date])
            
            # Fetch the results (if your procedure returns any)
            results = list(cursor.fetchall())  #Convert to list

            #Format results as a string (adjust formatting as needed)
            self.procedure_result = str(results)  #For simple results
            #Example using list comprehension for a formatted string
            #self.procedure_result = "\n".join([f"Row: {row}" for row in results])

            cursor.close()
            connection.close()
            self.error_message = ""  # Clear any previous errors

        except mysql.connector.Error as err:
            self.error_message = f"Database error: {err}"
            self.procedure_result = ""  #Clear the result if there is error

    def set_date(self, date: str):
        """Handle date changes from the date picker."""
        self.date = date #Update state when the date input changes
        self.procedure_result = "" #Clear the previous result


def index():
    return rx.vstack(
        rx.heading("Stored Procedure Executor"),
        rx.text("Enter Date (YYYY-MM-DD):"),

        rx.date_picker(
            value=State.date,  # Bind to State.date
            on_change=State.set_date, #Call set_date on date change
            color_scheme="red"
            ),

        rx.button("Execute Procedure", on_click=State.call_procedure),

        rx.cond(
            State.error_message != "",
            rx.text(State.error_message, color="red"), #Display error messages
            rx.cond(
                State.procedure_result != "",
                rx.text("Procedure Result:",font_weight="bold"),
                rx.text(""),#Empty text if no error and no result
            ),
        ),
        rx.cond(
            State.procedure_result != "",
            rx.text(State.procedure_result),  #Display the results
            rx.text(""),#Empty text if no error and no result
        ),

        spacing="1em",
    )

app = rx.App()
app.add_page(index)
app.compile()
