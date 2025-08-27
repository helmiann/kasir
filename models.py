from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Stok(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kode = db.Column(db.String, nullable=False)
    jenis = db.Column(db.String, nullable=False)
    nama = db.Column(db.String, nullable=False)
    harga = db.Column(db.Integer, nullable=False)
    jumlah = db.Column(db.Integer, nullable=False)
    minggu = db.Column(db.Date, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("kode", "minggu", name="unique_kode_per_minggu"),
    )

class Penjualan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kode = db.Column(db.String(20), nullable=False)  # 👈 tambahkan kolom kode
    nama = db.Column(db.String(100), nullable=False)
    jumlah = db.Column(db.Integer, nullable=False)
    harga = db.Column(db.Integer, nullable=False)
    tanggal = db.Column(db.DateTime, default=datetime.utcnow)
