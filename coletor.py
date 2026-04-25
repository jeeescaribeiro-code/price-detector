
"""
PriceDetector: Coletor Diário de Preços
"""
import sqlite3, random, os
from datetime import date

DB_PATH = os.getenv('PRICERADAR_DB', 'priceradar.db')
PRECOS_BASE   = {1:22.90,2:21.50,3:8.20,4:8.90,5:6.50,6:6.10,7:28.90,
                 8:4.50,9:18.90,10:8.90,11:15.90,12:14.50,13:12.90,
                 14:2.50,15:2.50,16:10.90}
FATOR_MERCADO = {1:0.92,2:1.05,3:1.00,4:1.08,5:0.95}

def setup_banco(conn):
    """Cria as tabelas se não existirem e popula dados base."""
    cur = conn.cursor()
    cur.executescript('''
    CREATE TABLE IF NOT EXISTS categorias(id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL UNIQUE, descricao TEXT);
    CREATE TABLE IF NOT EXISTS supermercados(id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL UNIQUE, cidade TEXT NOT NULL, bairro TEXT, ativo INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE IF NOT EXISTS produtos(id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL, marca TEXT, unidade TEXT NOT NULL, categoria_id INTEGER NOT NULL, FOREIGN KEY(categoria_id) REFERENCES categorias(id));
    CREATE TABLE IF NOT EXISTS precos(id INTEGER PRIMARY KEY AUTOINCREMENT, produto_id INTEGER NOT NULL, supermercado_id INTEGER NOT NULL, preco REAL NOT NULL, data_coleta TEXT NOT NULL DEFAULT(DATE("now")), em_promocao INTEGER NOT NULL DEFAULT 0, FOREIGN KEY(produto_id) REFERENCES produtos(id), FOREIGN KEY(supermercado_id) REFERENCES supermercados(id));
    CREATE INDEX IF NOT EXISTS idx_precos_data ON precos(data_coleta);
    ''')

    # Insere dados base apenas se vazios
    if cur.execute('SELECT COUNT(*) FROM categorias').fetchone()[0] == 0:
        cur.executemany('INSERT INTO categorias(nome,descricao) VALUES(?,?)',[
            ('Grãos e Cereais','Arroz, feijão...'),('Óleos e Gorduras','Óleos, azeite...'),
            ('Laticínios','Leite, queijo...'),('Carnes','Frango, bovina...'),
            ('Higiene Pessoal','Shampoo...'),('Limpeza','Detergente...')])
        cur.executemany('INSERT INTO supermercados(nome,cidade,bairro) VALUES(?,?,?)',[
            ('Atacadão','Uberlândia','Brasil'),('Bretas','Uberlândia','Centro'),
            ('Superpão','Uberlândia','Santa Mônica'),('Comper','Uberlândia','Tibery'),
            ("Sam's Club",'Uberlândia','Jardim Karaíba')])
        cur.executemany('INSERT INTO produtos(nome,marca,unidade,categoria_id) VALUES(?,?,?,?)',[
            ('Arroz Branco','Tio João','5kg',1),('Arroz Branco','Camil','5kg',1),
            ('Feijão Carioca','Camil','1kg',1),('Feijão Preto','Kicaldo','1kg',1),
            ('Macarrão Espaguete','Barilla','500g',1),
            ('Óleo de Soja','Liza','900ml',2),('Azeite Extra Virgem','Galo','500ml',2),
            ('Leite Integral','Itambé','1L',3),('Queijo Mussarela','Polenghi','500g',3),
            ('Manteiga','Aviação','200g',3),
            ('Peito de Frango','Sadia','1kg',4),('Patinho Moído','Friboi','500g',4),
            ('Shampoo','Pantene','400ml',5),('Sabonete','Dove','90g',5),
            ('Detergente','Ypê','500ml',6),('Sabão em Pó','OMO','1kg',6)])
        conn.commit()
        print('  Dados base inseridos!');


def coletar_dia(conn, hoje=None):
    """Insere os preços do dia."""
    if hoje is None:
        hoje = date.today()
    cur = conn.cursor()

    # Não duplica se já coletou hoje
    ja_coletou = cur.execute(
        'SELECT COUNT(*) FROM precos WHERE data_coleta = ?', (hoje.isoformat(),)
    ).fetchone()[0]
    if ja_coletou > 0:
        print(f'  Coleta de {hoje} já existe ({ja_coletou} registros). Pulando.')
        return 0

    from datetime import date as d_
    dias_desde = (hoje - d_(2024, 1, 1)).days
    inflacao   = 1 + (dias_desde / 30) * 0.003

    registros = []
    for pid, base in PRECOS_BASE.items():
        for sid, fator in FATOR_MERCADO.items():
            var   = random.uniform(-0.03, 0.03)
            preco = round(base * fator * inflacao * (1 + var), 2)
            promo = 0
            if random.random() < 0.08:
                preco = round(preco * (1 - random.uniform(0.10, 0.25)), 2)
                promo = 1
            registros.append((pid, sid, preco, hoje.isoformat(), promo))

    cur.executemany(
        'INSERT INTO precos(produto_id,supermercado_id,preco,data_coleta,em_promocao) VALUES(?,?,?,?,?)',
        registros
    )
    conn.commit()
    return len(registros)


if __name__ == '__main__':
    print(f'PriceRadar: Coleta diária iniciada')
    conn = sqlite3.connect(DB_PATH)
    setup_banco(conn)
    n = coletar_dia(conn)
    if n > 0:
        print(f'{n} registros inseridos para {date.today()}')
    total = conn.execute('SELECT COUNT(*) FROM precos').fetchone()[0]
    print(f'Total no banco: {total:,} registros')
    conn.close()
