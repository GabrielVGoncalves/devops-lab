import psycopg2

conn = psycopg2.connect(
    host="postgres",       # pense: qual hostname o flaskapp enxerga o postgres?
    port=5432,          # porta interna ou externa, considerando que é container→container?
    dbname="postgres",      # o nome do banco que você configurou no POSTGRES_DB (ou padrão)
    user="postgres",
    password="mypassword"
)

cursor = conn.cursor()   # qual método de "conn" cria esse objeto que executa SQL?

cursor.execute("SELECT * from requests;")  # um SELECT simples na tabela requests, ou até um SELECT 1 pra começar mais simples

resultado = cursor.fetchall()
print(resultado)

cursor.close()
conn.close()