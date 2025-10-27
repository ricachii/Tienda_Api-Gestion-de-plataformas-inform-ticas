import os, pymysql
from dotenv import load_dotenv
load_dotenv()
def get_conn():
    return pymysql.connect(
        host=os.getenv("DB_HOST","127.0.0.1"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        database=os.getenv("DB_NAME"),
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )
def listar_productos(conn, cat=None, q=None, page=1, size=12):
    where = []
    params = []
    if cat:
        where.append("categoria = %s")
        params.append(cat)
    if q:
        where.append("(nombre LIKE %s OR descripcion LIKE %s)")
        like = f"%{q}%"
        params.extend([like, like])

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    offset = (page - 1) * size

    with conn.cursor() as cur:
        # total
        cur.execute(f"SELECT COUNT(*) FROM productos {where_sql}", params)
        total = cur.fetchone()[0]

        # datos
        cur.execute(
            f"""SELECT id, nombre, precio, stock, categoria, imagen_url, descripcion
                FROM productos {where_sql}
                ORDER BY id
                LIMIT %s OFFSET %s""",
            params + [size, offset]
        )
        rows = cur.fetchall()

    items = [
        dict(
            id=r[0], nombre=r[1], precio=float(r[2]), stock=r[3],
            categoria=r[4], imagen_url=r[5], descripcion=r[6]
        )
        for r in rows
    ]
    return {"page": page, "size": size, "total": total, "items": items}
