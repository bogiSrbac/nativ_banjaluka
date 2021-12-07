from django.contrib import admin
from .models import Korisnik, Kupac, Prodaja, Faktura, Pozicija, Valute,  Ponuda, ProdajaPonuda


class ProdajaInline(admin.TabularInline):
    model = Prodaja

class FaktureAdmin(admin.ModelAdmin):
   list_display = ('broj_fakture', 'kupac', 'datum_fakture', 'rok_placanja', 'placeno', 'valuta', 'avansno_uplaceno', 'nacin_placanja', 'pdf', 'uplaceno', 'neto_cijena', 'bruto_cijena', 'pdv', 'razlika', 'bruto_cijena_km')
   fields = ['broj_fakture', 'kupac', ('datum_fakture', 'rok_placanja', 'placeno', 'valuta', 'avansno_uplaceno', 'nacin_placanja', 'pdf', 'uplaceno', 'neto_cijena', 'bruto_cijena', 'pdv', 'razlika', 'bruto_cijena_km')]
   inlines = [ProdajaInline]



admin.site.register(Korisnik)
admin.site.register(Kupac)
admin.site.register(Prodaja)
admin.site.register(Faktura, FaktureAdmin)
admin.site.register(Pozicija)
admin.site.register(Valute)
admin.site.register(Ponuda)
admin.site.register(ProdajaPonuda)
