__app_name__ = "tydo"
__version__ = "0.1.0"
__description__ = "A simple command-line todo application with reporting features."


(
    SUCCESS,
    DIR_ERROR,
    FILE_ERROR,
    DB_WRITE_ERROR,
    DB_READ_ERROR,
    JSON_ERROR,
    ID_ERROR,
) = range(7)


ERRORS = {
    DIR_ERROR: "Directory error: Unable to create or access the required directory.",
    FILE_ERROR: "File error: Unable to create or access the required file.",
    DB_WRITE_ERROR: "Database write error: Unable to write to the database.",
    DB_READ_ERROR: "Database read error: Unable to read from the database.",
    JSON_ERROR: "JSON error: Unable to parse or generate JSON data.",
    ID_ERROR: "ID error: Invalid or non-existent task ID provided.",
}
