from flask import Flask, render_template, request, redirect, url_for, request, send_file, session 
from models import db, Stok, Penjualan
from datetime import datetime, date, timedelta
from openpyxl import Workbook
from sqlalchemy import func
import io
import os

app = Flask(__name__)
cart = []
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "dev_secret")

# Konfigurasi database
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  
db.init_app(app)

# Buat tabel jika belum ada
with app.app_context():
    db.create_all()


@app.route("/")
def index():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    
    # ambil data stok dan cart untuk ditampilkan di kasir
    stocks = Stok.query.all()
    return render_template("index.html", cart=cart, stocks=stocks)



@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    kode = request.form["kode"].strip()  # ambil kode dari form
    jumlah = int(request.form["jumlah"])

    # cari stok berdasarkan kolom 'kode'
    stok = Stok.query.filter_by(kode=kode).first()

    if stok and stok.jumlah >= jumlah:
        subtotal = stok.harga * jumlah
        cart.append({
            "stok_id": stok.id,   # simpan id biar aman
            "kode": stok.kode,    # tampilkan kode barang
            "nama": stok.nama,
            "harga": stok.harga,
            "jumlah": jumlah,
            "subtotal": subtotal
        })
    else:
        # kalau stok tidak cukup atau tidak ada, bisa kasih flash message
        print("Barang tidak ditemukan atau stok tidak cukup")

    return redirect(url_for("index"))


@app.route("/checkout")
def checkout():
    if cart:
        for item in cart:
            stok = Stok.query.get(item["stok_id"])
            if stok and stok.jumlah >= item["jumlah"]:
                # kurangi stok
                stok.jumlah -= item["jumlah"]

                # simpan ke penjualan
                sale = Penjualan(
                kode=stok.kode,   # ganti id → kode
                nama=stok.nama,
                jumlah=item["jumlah"],
                harga=stok.harga
                )
                db.session.add(sale)

        db.session.commit()
        cart.clear()
    return redirect(url_for("index"))


@app.route("/sales")
def sales_page():
    all_sales = Penjualan.query.all()
    total = sum(s.jumlah * s.harga for s in all_sales)
    return render_template("sales.html", sales=all_sales, total=total)


@app.route("/stocks")
def stocks_page():
    all_stocks = Stok.query.all()
    return render_template("stocks.html", stocks=all_stocks)


@app.route("/add_stock", methods=["GET", "POST"])
def add_stock():
    if request.method == "POST":
        kode = request.form["kode"]
        jenis = request.form["jenis"]
        nama = request.form["nama"]
        harga = int(request.form["harga"])
        jumlah = int(request.form["jumlah"])

        minggu_input = request.form.get("minggu")
        if minggu_input:
            minggu = datetime.strptime(minggu_input, "%Y-%m-%d").date()
        else:
            # fallback: pakai minggu terakhir atau hari ini
            minggu_terakhir = db.session.query(Stok.minggu).order_by(Stok.minggu.desc()).first()
            minggu = minggu_terakhir[0] if minggu_terakhir else date.today()

        new_stock = Stok(
            kode=kode,
            jenis=jenis,
            nama=nama,
            harga=harga,
            jumlah=jumlah,
            minggu=minggu   # sudah pasti objek date, bukan string
        )
        db.session.add(new_stock)
        db.session.commit()
        return redirect(url_for("stocks_page"))

    has_minggu = db.session.query(Stok.minggu).first() is not None
    return render_template("add_stock.html", has_minggu=has_minggu)


@app.route("/update_stock/<int:id>", methods=["POST"])
def update_stock(id):
    stok = Stok.query.get(id)
    if not stok:
        return "Stok tidak ditemukan!", 404

    action = request.form.get("action")
    if action == "add":
        stok.jumlah += 1
    elif action == "sub":
        if stok.jumlah > 0:
            stok.jumlah -= 1
    elif action == "delete":
        db.session.delete(stok)
        db.session.commit()
        return redirect(url_for("stocks_page"))

    db.session.commit()
    return redirect(url_for("stocks_page"))


@app.route("/tambah_minggu", methods=["POST"])
def tambah_minggu():
    tanggal_minggu_baru_str = request.form.get("minggu")  # contoh input: 2025-09-01
    if not tanggal_minggu_baru_str:
        return "Tanggal minggu harus diisi!", 400

    try:
        tanggal_minggu_baru = datetime.strptime(tanggal_minggu_baru_str, "%Y-%m-%d").date()
    except ValueError:
        return "Format tanggal tidak valid! Gunakan YYYY-MM-DD", 400

    # cek apakah minggu baru sudah ada
    if Stok.query.filter_by(minggu=tanggal_minggu_baru).first():
        return f"Minggu {tanggal_minggu_baru} sudah ada!", 400

    # ambil minggu aktif terakhir dari session
    minggu_aktif_terakhir_str = session.get("minggu_aktif")
    if minggu_aktif_terakhir_str:
        try:
            minggu_aktif_terakhir = datetime.strptime(minggu_aktif_terakhir_str, "%Y-%m-%d").date()
        except ValueError:
            # kalau format lama tidak sesuai, ambil minggu terakhir dari DB
            last_minggu = db.session.query(Stok.minggu).order_by(Stok.minggu.desc()).first()
            if not last_minggu:
                return "Belum ada data stok awal!", 400
            minggu_aktif_terakhir = last_minggu[0]
    else:
        # jika session kosong, ambil minggu terakhir dari DB
        last_minggu = db.session.query(Stok.minggu).order_by(Stok.minggu.desc()).first()
        if not last_minggu:
            return "Belum ada data stok awal!", 400
        minggu_aktif_terakhir = last_minggu[0]

    # pastikan minggu baru lebih besar dari minggu aktif terakhir
    if tanggal_minggu_baru <= minggu_aktif_terakhir:
        return f"Minggu baru ({tanggal_minggu_baru}) harus lebih besar dari minggu aktif terakhir ({minggu_aktif_terakhir})", 400

    # ambil semua stok dari minggu aktif terakhir
    stok_terakhir = Stok.query.filter_by(minggu=minggu_aktif_terakhir).all()
    if not stok_terakhir:
        return "Belum ada stok di minggu aktif!", 400

    # duplikasi stok ke minggu baru
    for s in stok_terakhir:
        duplikat = Stok(
            kode=s.kode,
            jenis=s.jenis,
            nama=s.nama,
            harga=s.harga,
            jumlah=s.jumlah,            # stok terakhir setelah transaksi
            minggu=tanggal_minggu_baru  # snapshot minggu baru
        )
        db.session.add(duplikat)

    db.session.commit()

    # update minggu aktif di session ke minggu baru (simpan string YYYY-MM-DD)
    session["minggu_aktif"] = tanggal_minggu_baru.strftime("%Y-%m-%d")

    # hapus minggu paling lama jika lebih dari 4 snapshot
    minggu_unik = [m[0] for m in db.session.query(Stok.minggu).distinct().order_by(Stok.minggu.asc()).all()]
    if len(minggu_unik) > 4:
        minggu_dihapus = minggu_unik[0]
        Stok.query.filter_by(minggu=minggu_dihapus).delete()
        db.session.commit()

    return f"Snapshot minggu {tanggal_minggu_baru} berhasil ditambahkan!"

@app.route("/export_sales")
def export_sales():
    # ambil parameter tanggal dari query string, contoh: /export_sales?start=2025-08-01&end=2025-08-31
    start_date_str = request.args.get("start")
    end_date_str = request.args.get("end")

    if not start_date_str or not end_date_str:
        return "Harap masukkan start dan end (format: YYYY-MM-DD)", 400

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d") + timedelta(days=1) - timedelta(seconds=1)
    except ValueError:
        return "Format tanggal salah, gunakan YYYY-MM-DD", 400

    # query data penjualan sesuai range
    sales = Penjualan.query.filter(
    Penjualan.tanggal >= start_date,
    Penjualan.tanggal < end_date
    ).all()


    # buat workbook excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Penjualan"

    # header
    ws.append(["Kode", "Nama", "Jumlah", "Harga", "Subtotal", "Tanggal"])

    # isi data
    for s in sales:
        ws.append([
            s.kode,
            s.nama,
            s.jumlah,
            s.harga,
            s.jumlah * s.harga,
            s.tanggal.strftime("%Y-%m-%d %H:%M:%S")
        ])

    # total
    total = sum(s.jumlah * s.harga for s in sales)
    ws.append([])
    ws.append(["", "", "", "TOTAL", total])

    # simpan ke memory
    file_stream = io.BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    filename = f"penjualan_{start_date_str}_to_{end_date_str}.xlsx"

    return send_file(
        file_stream,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # cek kredensial
        if username == "sportbrand" and password == "jejasalto21":
            session["logged_in"] = True
            return redirect(url_for("index"))
        else:
            return "Username atau password salah!", 401

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))

@app.route("/hapus_stok/<int:id>", methods=["POST"])
def hapus_stok(id):
    stok = Stok.query.get(id)
    if not stok:
        return "Stok tidak ditemukan!", 404

    db.session.delete(stok)
    db.session.commit()
    return redirect(url_for("stocks"))  # kembali ke halaman stok

@app.route("/export_stok")
def export_stok():
    # ambil semua stok
    all_stok = Stok.query.order_by(Stok.kode, Stok.minggu).all()
    
    if not all_stok:
        return "Belum ada data stok!", 400

    # bikin pivot dictionary: {kode: {minggu: jumlah}}
    pivot_data = {}
    minggu_unik = sorted(list({s.minggu for s in all_stok}))
    
    for s in all_stok:
        if s.kode not in pivot_data:
            pivot_data[s.kode] = {
                "nama": s.nama,
                "jenis": s.jenis,
                "harga": s.harga
            }
        pivot_data[s.kode][s.minggu] = s.jumlah

    # buat workbook excel
    wb = Workbook()
    ws = wb.active
    ws.title = "Stok Pivot"

    # header
    header = ["Kode", "Nama", "Jenis", "Harga"] + [str(m) for m in minggu_unik]
    ws.append(header)

    # isi data
    for kode, data in pivot_data.items():
        row = [kode, data["nama"], data["jenis"], data["harga"]]
        for m in minggu_unik:
            row.append(data.get(m, 0))  # jika stok tidak ada, isi 0
        ws.append(row)

    # simpan ke memory
    file_stream = io.BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    return send_file(
        file_stream,
        as_attachment=True,
        download_name="stok_pivot.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
    app.run(debug=True)

