import sqlite3

con = sqlite3.connect("esvitlo.db", detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
cur = con.cursor()


