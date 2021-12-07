from django.shortcuts import render

# Create your views here.
import os
from django.conf import settings
from os import listdir
from os.path import isfile, join
from weasyprint import HTML, CSS
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import View, ListView, UpdateView, DetailView, CreateView, DeleteView, TemplateView
from django.db.models import Sum, Q
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from .models import Korisnik, Kupac, Faktura, Prodaja, Pozicija, Valute, Ponuda, ProdajaPonuda
from django.template.loader import get_template, render_to_string
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse_lazy, reverse
from .forms import FakturaForma, ProdajaForma, PonudaForma, PonudaProdajaForma, FakturaUpdateForm, FakturaUpdateFormPlaceno
from django.utils.dateformat import DateFormat
from django.core.files.base import ContentFile
import xlwt, xlsxwriter, io
import datetime


def pdf_generator(request, pk):
    faktura = Faktura.objects.get(id=pk)
    prodaja = Prodaja.objects.filter(faktura__id=pk)
    prodaja_do_8 = Prodaja.objects.filter(faktura__id=pk)[:8]
    prodaja_8 = Prodaja.objects.filter(faktura__id=pk)[8:]
    prodaja_do_16 = Prodaja.objects.filter(faktura__id=pk)[8:24]
    prodaja_16 = Prodaja.objects.filter(faktura__id=pk)[24:]
    neto_suma = Prodaja.objects.filter(faktura__id=pk).aggregate(net_suma=Sum('neto_cijena'))
    bruto_suma = Prodaja.objects.filter(faktura__id=pk).aggregate(brt_suma=Sum('bruto_cijena'))
    formatirano1= round(neto_suma['net_suma'], 2)
    formatirano = round(bruto_suma['brt_suma'], 2)
    bruto_suma['brt_suma'] = formatirano
    neto_suma['net_suma'] = formatirano1
    prodaja_count = len(prodaja)
    korisnik = Korisnik.objects.get(username=request.user.username)
    valuta = Valute.objects.get(valute='EUR')
    avans = faktura.avansno_uplaceno
    bruto_suma_avans = bruto_suma['brt_suma'] - avans
    bruto_razlika = bruto_suma['brt_suma'] -  neto_suma['net_suma']
    image = settings.STATIC_ROOT+'slike/logo_nativ.png'
    valuta_bam = Valute.objects.get(valute='BAM')
    bruto_suma_bam = round(bruto_suma['brt_suma'] * valuta_bam.bam_evro, 2)
    datum = DateFormat(faktura.datum_fakture)
    datum1 = datum.format('Ymd')
    count = 0
    pdv = []
    for p in prodaja:
        pdv.append(p.pdv)
        count += 1
        if count == 1:
            break;
    faktura.pdf.delete()
    context = {
        'korisnik': korisnik,
        'faktura': faktura,
        'prodaja': prodaja,
        'prodaja_5': prodaja[4:],
        'prodaja_24_40':prodaja[24:40],
        'prodaja_40_52':prodaja[40:52],
        'prodaja_8': prodaja_8,
        'prodaja_do_8': prodaja_do_8,
        'prodaja_do_16': prodaja_do_16,
        'prodaja_16': prodaja_16,
        'neto_suma': neto_suma,
        'bruto_suma': bruto_suma,
        'm': '1111',
        'prodaja_count': prodaja_count,
        'valuta':valuta,
        'avans': avans,
        'bruto_avans':bruto_suma_avans,
        'bruto_razlika': bruto_razlika,
        'image': image,
        'bruto_suma_bam': bruto_suma_bam,
        'valute_bam': valuta_bam,
        'pdv': pdv[0],

    }



    html_template = render_to_string('fakture/faktura_html.html', context)
    instance = get_object_or_404(Faktura.objects.filter(pk=pk))

    pdf_file = HTML(string=html_template,  base_url = request.build_absolute_uri()).write_pdf(stylesheets=[CSS(settings.STATIC_ROOT + 'css/style.css')],  presentational_hints=True)
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = 'filename="Faktura broj: IN-{}-{}-{}.pdf"'.format(faktura.broj_fakture, datum1, faktura.ident_brojevi)
    pdf =ContentFile(pdf_file)
    if not instance.pdf:
        instance.pdf.save('IN-{}-{}-{}.pdf'.format(faktura.broj_fakture, datum1, faktura.ident_brojevi), pdf)
    return response




@login_required
#@permission_required
def pocetna_stranica(request):
    context = {}

    if Faktura.objects.filter(broj_fakture__isnull=True):
        pass
    else:
        fakture = Faktura.objects.filter(broj_fakture__isnull=False).order_by('-broj_fakture')
        #datum = Faktura.objects.values(Year=TruncYear('datum_fakture')).distinct()
        datum = Faktura.objects.dates('datum_fakture', 'year')
        valute = Valute.objects.all().order_by('valute')

        context = {
            'fakture':fakture,
            'datum':datum,
            'valute': valute,


        }

    return render(request, 'bazni_template.html', context)

def base(request):
    return render(request, 'fakture/base_nativ.html', {})

class KreirajValute(LoginRequiredMixin, CreateView):
    model = Valute
    fields = '__all__'
    template_name = 'fakture/valute_create.html'
    success_url = reverse_lazy('fakture:kreiraj-valutu')

    def get_context_data(self, *args, **kwargs):
        context = super(KreirajValute, self).get_context_data(**kwargs)
        context['valute'] = Valute.objects.all().order_by('valute')
        return context

class ValuteUpdate(LoginRequiredMixin, UpdateView):
    model = Valute
    fields = ('bam_evro',)
    template_name = 'fakture/valuta_update.html'

    def get_success_url(self):
        return reverse_lazy('fakture:index')

class FaktureLista(LoginRequiredMixin, ListView):
    model = Faktura
    template_name = 'fakture/faktura_list.html'

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super(FaktureLista, self).get_context_data(**kwargs)
        context['datum'] = Faktura.objects.dates('datum_fakture', 'year')
        context['valute'] = Valute.objects.all()
        context['kupci'] = Kupac.objects.all()
        context['pozicije'] = Pozicija.objects.all()
        return context

class FaktureDetail(LoginRequiredMixin, DetailView):
    model = Faktura
    template_name = 'fakture/fakture_detail.html'

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super(FaktureDetail, self).get_context_data(**kwargs)
        bf = Faktura.objects.get(id=self.kwargs['pk'])
        proodaja = Prodaja.objects.filter(faktura_id=bf)
        context['faktura'] = Faktura.objects.get(id=self.kwargs['pk'])
        context['datum'] = Faktura.objects.dates('datum_fakture', 'year')
        context['pozicije'] = Pozicija.objects.all()
        context['prodaja'] = proodaja
        return context

@login_required
def faktura_po_godinama(request, year):
    fakture = Faktura.objects.filter(datum_fakture__year=year)

    return render(request, 'fakture/godina_fakture.html', {'fakture':fakture})

class KreirajFakturu(LoginRequiredMixin, CreateView):
    model = Faktura
    form_class = FakturaForma
    template_name = 'fakture/faktura_create.html'
    success_url = reverse_lazy('fakture:faktura-prodaja')

    def get_initial(self):
        if not Faktura.objects.filter(broj_fakture__isnull=False).exists():
            faktura = '0001'
            return {'broj_fakture': faktura}
        else:
            broj = Faktura.objects.filter(broj_fakture__isnull=False).order_by('-pk')[0]
            faktura1 = int(broj.broj_fakture)
            if faktura1 <= 9:
                faktura = '000'+ str(faktura1+1)
                return {'broj_fakture': faktura}
            elif 10 <= faktura1 <= 99:
                faktura = '00' + str(faktura1+1)
                return {'broj_fakture': faktura}
            elif 100 <= faktura1 <= 999:
                faktura = '0'+str(faktura1+1)
                return {'broj_fakture': faktura}
    def get_context_data(self, **kwargs):
        context = super(KreirajFakturu, self).get_context_data(**kwargs)
        context['valute'] = Valute.objects.all()
        context['kupci'] = Kupac.objects.all()
        context['pozicije'] = Pozicija.objects.all()
        return context

    def get_success_url(self):
        return reverse('fakture:faktura-prodaja', args={self.object.pk})



class KreirajFakturuProdaja(LoginRequiredMixin, CreateView):
    form_class = ProdajaForma
    template_name = 'fakture/faktura_create_nastavak.html'
    success_url = reverse_lazy('fakture:faktura-prodaja')
    def get_initial(self, **kwargs):
        if Faktura.objects.filter(broj_fakture__isnull=True):
            faktura = '0001'
        else:
            broj = Faktura.objects.get(id=self.kwargs['pk'])
            faktura = broj
        return {'faktura':faktura}

    def get_context_data(self, **kwargs):
        context = super(KreirajFakturuProdaja, self).get_context_data(**kwargs)
        faktura = Faktura.objects.get(id=self.kwargs['pk'])
        neto_suma = Prodaja.objects.filter(faktura_id=faktura.pk).aggregate(net_suma=Sum('neto_cijena'))
        bruto_suma = Prodaja.objects.filter(faktura__id=faktura.pk).aggregate(brt_suma=Sum('bruto_cijena'))

        context['faktura']= Faktura.objects.get(id=self.kwargs['pk'])
        context['prodaja'] = Prodaja.objects.all().filter(faktura__id=faktura.pk)
        context['neto_suma'] = neto_suma
        context['bruto_suma'] = bruto_suma
        context['pozicije'] = Pozicija.objects.all()
        return context
    def get_success_url(self):
        return reverse('fakture:faktura-prodaja', kwargs={'pk':self.object.faktura.pk})

class ProdajaDetalji(LoginRequiredMixin, DetailView):
    model = Prodaja
    template_name = 'fakture/prodaja_detail.html'
    def get_success_url(self):
        return reverse('fakture:faktura-prodaja', args={self.object.pk})

class ProdajaIzmjena(LoginRequiredMixin, UpdateView):
    model = Prodaja
    fields = '__all__'
    template_name = 'fakture/update_prodaja.html'
    def get_success_url(self):
        return reverse('fakture:faktura-prodaja', kwargs={'pk':self.object.faktura.pk})

class FakturaUpdate(LoginRequiredMixin, UpdateView):
    model = Faktura
    form_class = FakturaUpdateForm
    template_name = 'fakture/faktura_update.html'
    success_url = reverse_lazy('fakture:faktura-prodaja-izmjena')

    def get_success_url(self):
        return reverse('fakture:faktura-prodaja', args={self.object.pk})

class ProdajaGlavnaUpdate(LoginRequiredMixin, UpdateView):
    model = Prodaja
    form_class = ProdajaForma
    template_name = 'fakture/prodaja_glavna_update.html'
    success_url = reverse_lazy('fakture:faktura-prodaja-izmjena')


    def get_context_data(self, **kwargs):
        context = super(ProdajaGlavnaUpdate, self).get_context_data(**kwargs)
        faktura = Faktura.objects.get(id=self.kwargs['pk'])
        neto_suma = Prodaja.objects.filter(faktura__broj_fakture=faktura.broj_fakture).aggregate(
            net_suma=Sum('neto_cijena'))
        bruto_suma = Prodaja.objects.filter(faktura__broj_fakture=faktura.broj_fakture).aggregate(
            brt_suma=Sum('bruto_cijena'))

        context['faktura'] = Faktura.objects.get(id=self.kwargs['pk'])
        context['prodaja'] = Prodaja.objects.all().filter(faktura__broj_fakture=faktura.broj_fakture)
        context['neto_suma'] = neto_suma
        context['bruto_suma'] = bruto_suma
        return context

    def get_success_url(self):
        return reverse('fakture:faktura-prodaja-izmjena', kwargs={'pk': self.object.faktura.pk})



def faktura_skica_gotova(request, pk):
    faktura = Faktura.objects.get(id=pk)
    prodaja = Prodaja.objects.filter(faktura_id=pk)
    prodaja_do_8 = Prodaja.objects.filter(faktura_id=pk)[:8]
    prodaja_8 = Prodaja.objects.filter(faktura_id=pk)[8:]
    prodaja_do_16 = Prodaja.objects.filter(faktura_id=pk)[8:24]
    prodaja_16 = Prodaja.objects.filter(faktura_id=pk)[24:]
    neto_suma = Prodaja.objects.filter(faktura_id=pk).aggregate(net_suma=Sum('neto_cijena'))
    bruto_suma = Prodaja.objects.filter(faktura_id=pk).aggregate(brt_suma=Sum('bruto_cijena'))
    formatirano1= round(neto_suma['net_suma'], 2)
    formatirano = round(bruto_suma['brt_suma'], 2)
    bruto_suma['brt_suma'] = formatirano
    neto_suma['net_suma'] = formatirano1
    prodaja_count = len(prodaja)
    korisnik = Korisnik.objects.get(username=request.user.username)
    valuta = Valute.objects.get(valute='EUR')
    avans = faktura.avansno_uplaceno
    bruto_suma_avans = bruto_suma['brt_suma'] - avans
    bruto_razlika = bruto_suma['brt_suma'] - neto_suma['net_suma']
    valuta_bam = Valute.objects.get(valute='BAM')
    bruto_suma_bam = round(bruto_suma['brt_suma'] * valuta_bam.bam_evro, 2)

    context = {
        'korisnik': korisnik,
        'faktura': faktura,
        'prodaja': prodaja,
        'prodaja_5': prodaja[4:],
        'prodaja_24_40':prodaja[24:40],
        'prodaja_40_52':prodaja[40:52],
        'prodaja_8': prodaja_8,
        'prodaja_do_8': prodaja_do_8,
        'prodaja_do_16': prodaja_do_16,
        'prodaja_16': prodaja_16,
        'neto_suma': neto_suma,
        'bruto_suma': bruto_suma,
        'm': '1111',
        'prodaja_count': prodaja_count,
        'valuta':valuta,
        'avans': avans,
        'bruto_avans':bruto_suma_avans,
        'bruto_razlika': bruto_razlika,
        'bruto_suma_bam': bruto_suma_bam,
        'valute_bam': valuta_bam,
    }


    return render(request, 'fakture/faktura_skica_gotovo.html', context)

class ProdajaBrisanje(LoginRequiredMixin, DeleteView):
    model = Prodaja
    success_url = reverse_lazy('fakture:faktura-prodaja')
    template_name = 'fakture/prodaja_delete.html'

    def get_success_url(self):
        return reverse('fakture:faktura-prodaja', kwargs={'pk': self.object.faktura.pk})

class KupciLista(LoginRequiredMixin, ListView):
    model = Kupac
    template_name = 'fakture/kupac_list.html'

    def get_context_data(self, *args, **kwargs):
        context = super(KupciLista, self).get_context_data(**kwargs)
        context['zemlja'] = Kupac.objects.values('drzava').order_by('drzava').distinct()
        return context

class KupacNovi(LoginRequiredMixin, CreateView):
    model = Kupac
    fields = '__all__'
    template_name = 'fakture/kupac_create.html'
    success_url = reverse_lazy('fakture:lista-kupci')

class KupacUpdate(LoginRequiredMixin, UpdateView):
    model = Kupac
    fields = '__all__'
    template_name = 'fakture/kupac_izmjeni.html'
    success_url = reverse_lazy('fakture:kupac-detalji')

    def get_success_url(self):
        return reverse('fakture:kupac-detalji', kwargs={'pk': self.object.pk})

class KupacDetalji(LoginRequiredMixin, DetailView):
    model = Kupac
    template_name = 'fakture/kupac_detalji.html'

class PozicijaLista(LoginRequiredMixin, ListView):
    model = Pozicija
    template_name = "fakture/poyicije_list.html"

class PozicijaKreiraj(LoginRequiredMixin, CreateView):
    model = Pozicija
    fields = '__all__'
    template_name = 'fakture/pozicija_kreiraj.html'
    success_url = reverse_lazy('fakture:pozicije-lista')

class PozicijaUpdate(LoginRequiredMixin, UpdateView):
    model = Pozicija
    fields = '__all__'
    template_name = 'fakture/pozicije_update.html'
    success_url = reverse_lazy('fakture:pozicije-lista')


class PonudaLista(LoginRequiredMixin, ListView):
    model = Ponuda
    template_name = 'fakture/ponuda_list.html'

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super(PonudaLista, self).get_context_data(**kwargs)
        context['datum'] = Ponuda.objects.dates('datum_ponude', 'year')
        context['valute'] = Valute.objects.all()
        context['kupci'] = Kupac.objects.all()
        context['pozicije'] = Pozicija.objects.all()
        return context

class PonudaDetail(LoginRequiredMixin, DetailView):
    model = Ponuda
    template_name = 'fakture/ponuda_detail.html'

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super(PonudaDetail, self).get_context_data(**kwargs)
        bf = Ponuda.objects.get(id=self.kwargs['pk'])
        proodaja = ProdajaPonuda.objects.filter(ponuda_id=bf)
        context['ponuda'] = Ponuda.objects.get(id=self.kwargs['pk'])
        context['datum'] = Ponuda.objects.dates('datum_ponude', 'year')
        context['pozicije'] = Pozicija.objects.all()
        context['prodaja'] = proodaja
        return context

class KreirajPonudu(LoginRequiredMixin, CreateView):
    model = Ponuda
    form_class = PonudaForma
    template_name = 'fakture/ponuda_create.html'
    success_url = reverse_lazy('fakture:ponuda-prodaja')

    def get_initial(self):
        if not Ponuda.objects.filter(broj_ponude__isnull=False).exists():
            faktura = '0001'
            return {'broj_ponude': faktura}
        else:
            broj = Ponuda.objects.filter(broj_ponude__isnull=False).order_by('-pk')[0]
            faktura1 = int(broj.broj_ponude)
            if faktura1 <= 9:
                faktura = '000'+ str(faktura1+1)
                return {'broj_ponude': faktura}
            elif 10 <= faktura1 <= 99:
                faktura = '00' + str(faktura1+1)
                return {'broj_ponude': faktura}
            elif 100 <= faktura1 <= 999:
                faktura = '0'+str(faktura1+1)
                return {'broj_ponude': faktura}
    def get_context_data(self, **kwargs):
        context = super(KreirajPonudu, self).get_context_data(**kwargs)
        context['valute'] = Valute.objects.all()
        context['kupci'] = Kupac.objects.all()
        return context

    def get_success_url(self):
        return reverse('fakture:ponuda-prodaja', args={self.object.pk})

class KreirajPonuduProdaja(LoginRequiredMixin, CreateView):
    form_class = PonudaProdajaForma
    template_name = 'fakture/ponuda_create_nastavak.html'
    success_url = reverse_lazy('fakture:ponuda-prodaja')
    def get_initial(self, **kwargs):
        if Ponuda.objects.filter(broj_ponude__isnull=True):
            faktura = '0001'
        else:
            broj = Ponuda.objects.get(id=self.kwargs['pk'])
            faktura = broj
        return {'ponuda':faktura}

    def get_context_data(self, **kwargs):
        context = super(KreirajPonuduProdaja, self).get_context_data(**kwargs)
        ponuda = Ponuda.objects.get(id=self.kwargs['pk'])
        neto_suma = ProdajaPonuda.objects.filter(ponuda_id=ponuda.pk).aggregate(net_suma=Sum('neto_cijena'))
        bruto_suma = ProdajaPonuda.objects.filter(ponuda_id=ponuda.pk).aggregate(brt_suma=Sum('bruto_cijena'))

        context['ponuda']= Ponuda.objects.get(id=self.kwargs['pk'])
        context['prodaja'] = ProdajaPonuda.objects.all().filter(ponuda_id=ponuda.pk)
        context['neto_suma'] = neto_suma
        context['bruto_suma'] = bruto_suma
        context['pozicije'] = Pozicija.objects.all()
        return context
    def get_success_url(self):
        return reverse('fakture:ponuda-prodaja', kwargs={'pk':self.object.ponuda.pk})

class ProdajaPonudaDetalji(LoginRequiredMixin, DetailView):
    model = ProdajaPonuda
    template_name = 'fakture/ponuda_prodaja_detail.html'
    def get_success_url(self):
        return reverse('fakture:ponuda-prodaja', args={self.object.pk})

def ponuda_skica_gotova(request, pk):
    ponuda = Ponuda.objects.get(id=pk)
    prodaja = ProdajaPonuda.objects.filter(ponuda_id=pk)
    prodaja_do_8 = ProdajaPonuda.objects.filter(ponuda_id=pk)[:8]
    prodaja_8 = ProdajaPonuda.objects.filter(ponuda_id=pk)[8:]
    prodaja_do_16 = ProdajaPonuda.objects.filter(ponuda_id=pk)[8:24]
    prodaja_16 = ProdajaPonuda.objects.filter(ponuda_id=pk)[24:]
    neto_suma = ProdajaPonuda.objects.filter(ponuda_id=pk).aggregate(net_suma=Sum('neto_cijena'))
    bruto_suma = ProdajaPonuda.objects.filter(ponuda_id=pk).aggregate(brt_suma=Sum('bruto_cijena'))
    formatirano1= round(neto_suma['net_suma'], 2)
    formatirano = round(bruto_suma['brt_suma'], 2)
    bruto_suma['brt_suma'] = formatirano
    neto_suma['net_suma'] = formatirano1
    prodaja_count = len(prodaja)
    korisnik = Korisnik.objects.get(username=request.user.username)
    valuta = Valute.objects.get(valute='EUR')
    avans = ponuda.avansno_uplaceno
    bruto_suma_avans = bruto_suma['brt_suma'] - avans
    bruto_razlika = bruto_suma['brt_suma'] - neto_suma['net_suma']
    valuta_bam = Valute.objects.get(valute='BAM')
    bruto_suma_bam = round(bruto_suma['brt_suma'] * valuta_bam.bam_evro, 2)

    context = {
        'korisnik': korisnik,
        'ponuda': ponuda,
        'prodaja': prodaja,
        'prodaja_5': prodaja[4:],
        'prodaja_24_40':prodaja[24:40],
        'prodaja_40_52':prodaja[40:52],
        'prodaja_8': prodaja_8,
        'prodaja_do_8': prodaja_do_8,
        'prodaja_do_16': prodaja_do_16,
        'prodaja_16': prodaja_16,
        'neto_suma': neto_suma,
        'bruto_suma': bruto_suma,
        'm': '1111',
        'prodaja_count': prodaja_count,
        'valuta':valuta,
        'avans': avans,
        'bruto_avans':bruto_suma_avans,
        'bruto_razlika': bruto_razlika,
        'bruto_suma_bam': bruto_suma_bam,
        'valute_bam': valuta_bam,
    }


    return render(request, 'fakture/ponuda_skica_gotovo.html', context)

def pdf_generator_ponuda(request, pk):
    ponuda = Ponuda.objects.get(id=pk)
    prodaja = ProdajaPonuda.objects.filter(ponuda_id=pk)
    prodaja_do_8 = ProdajaPonuda.objects.filter(ponuda_id=pk)[:8]
    prodaja_8 = ProdajaPonuda.objects.filter(ponuda_id=pk)[8:]
    prodaja_do_16 = ProdajaPonuda.objects.filter(ponuda_id=pk)[8:24]
    prodaja_16 = ProdajaPonuda.objects.filter(ponuda_id=pk)[24:]
    neto_suma = ProdajaPonuda.objects.filter(ponuda_id=pk).aggregate(net_suma=Sum('neto_cijena'))
    bruto_suma = ProdajaPonuda.objects.filter(ponuda_id=pk).aggregate(brt_suma=Sum('bruto_cijena'))
    formatirano1 = round(neto_suma['net_suma'], 2)
    formatirano = round(bruto_suma['brt_suma'], 2)
    bruto_suma['brt_suma'] = formatirano
    neto_suma['net_suma'] = formatirano1
    prodaja_count = len(prodaja)
    korisnik = Korisnik.objects.get(username=request.user.username)
    valuta = Valute.objects.get(valute='EUR')
    avans = ponuda.avansno_uplaceno
    bruto_suma_avans = bruto_suma['brt_suma'] - avans
    bruto_razlika = bruto_suma['brt_suma'] - neto_suma['net_suma']
    image = settings.STATIC_ROOT+'slike/logo_nativ.png'
    valuta_bam = Valute.objects.get(valute='BAM')
    bruto_suma_bam = round(bruto_suma['brt_suma'] * valuta_bam.bam_evro, 2)
    datum = DateFormat(ponuda.datum_ponude)
    datum1 = datum.format('Ymd')
    count = 0
    pdv = []
    for p in prodaja:
        pdv.append(p.pdv)
        count += 1
        if count == 1:
            break;
    ponuda.pdf.delete()

    context = {
        'korisnik': korisnik,
        'ponuda': ponuda,
        'prodaja': prodaja,
        'prodaja_5': prodaja[4:],
        'prodaja_24_40': prodaja[24:40],
        'prodaja_40_52': prodaja[40:52],
        'prodaja_8': prodaja_8,
        'prodaja_do_8': prodaja_do_8,
        'prodaja_do_16': prodaja_do_16,
        'prodaja_16': prodaja_16,
        'neto_suma': neto_suma,
        'bruto_suma': bruto_suma,
        'm': '1111',
        'prodaja_count': prodaja_count,
        'valuta': valuta,
        'avans': avans,
        'bruto_avans': bruto_suma_avans,
        'bruto_razlika': bruto_razlika,
        'image': image,
        'bruto_suma_bam': bruto_suma_bam,
        'valute_bam': valuta_bam,
        'pdv': pdv[0],
    }



    html_template = render_to_string('fakture/ponuda_pdf.html', context)
    instance = get_object_or_404(Ponuda.objects.filter(pk=pk))
    pdf_file = HTML(string=html_template,  base_url = request.build_absolute_uri()).write_pdf(stylesheets=[CSS(settings.STATIC_ROOT + 'css/style.css')],  presentational_hints=True)
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = 'filename="Ponuda broj: IN-{}-{}-{}.pdf"'.format(ponuda.broj_ponude, datum1, ponuda.ident_brojevi)
    pdf =ContentFile(pdf_file)
    if not instance.pdf:
        instance.pdf.save('OF-{}-{}-{}.pdf'.format(ponuda.broj_ponude, datum1, ponuda.ident_brojevi), pdf)
    return response

class PonudaUpdate(LoginRequiredMixin, UpdateView):
    model = Ponuda
    fields = '__all__'
    template_name = 'fakture/ponuda_update.html'


    def get_success_url(self):
        return reverse('fakture:ponuda-prodaja', args={self.object.pk})

class PonudaProdajaBrisanje(LoginRequiredMixin, DeleteView):
    model = ProdajaPonuda
    success_url = reverse_lazy('fakture:ponuda-prodaja')
    template_name = 'fakture/prodaja-delite.html'

    def get_success_url(self):
        return reverse('fakture:ponuda-prodaja', kwargs={'pk': self.object.pk})


class PonudaProdajaIzmjena(LoginRequiredMixin, UpdateView):
    model = ProdajaPonuda
    fields = '__all__'
    template_name = 'fakture/ponuda-prodaja-izmjena.html'

    def get_success_url(self):
        return reverse('fakture:ponuda-prodaja', kwargs={'pk':self.object.ponuda.pk})

@login_required
def ponude_po_godinama(request, year):
    ponuda = Ponuda.objects.filter(datum_ponude__year=year)

    return render(request, 'fakture/ponuda_godine.html', {'ponuda':ponuda})

class MojiPDF(LoginRequiredMixin, TemplateView):
    template_name = "fakture/lista_pdf_files.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # List of files in your MEDIA_ROOT
        media_path = settings.MEDIA_ROOT + '/pdf/'
        myfiles = [f for f in listdir(media_path) if isfile(join(media_path, f))]
        context['myfiles'] = myfiles


        return context

@login_required
def pregled_placenih_faktura_godine(request):
    datum = Faktura.objects.dates('datum_fakture', 'year').distinct()
    fakture = Faktura.objects.all()
    context = {'fakture': fakture,
               'datum':datum
               }
    return render(request, 'fakture/pregled_faktura_po_godinama_gotove.html', context)

@login_required
def pregled_placenih_faktura(request, year):
    fakture = Faktura.objects.all().filter(datum_fakture__year=year)
    datum1 = Faktura.objects.all().filter(datum_fakture__year=year)[0]
    datum = datum1.datum_fakture
    context = {'fakture': fakture, 'datum':datum}
    return render(request, 'fakture/pregled_placenih_faktura.html', context)

class FakturePlaceneUpdate(LoginRequiredMixin, UpdateView):
    model = Faktura
    form_class = FakturaUpdateFormPlaceno
    template_name = 'fakture/placene_fakture_update.html'

    def get_success_url(self):
        return reverse_lazy('fakture:placene-fakture', kwargs={'year': self.object.datum_fakture.year})


@login_required
def export_users_xls(request, year):

    output = io.BytesIO()

    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet()
    columns = ['Broj fakture', 'Datum fakture', 'Komitent', 'Iznos neto', 'PDV 17%', 'Ukupan iznos u Evrima', 'Ukupan iznos u KM', 'Uplaćeno', 'Rok plaćanja',  'Razlika', 'Realizovano', ]

    data = Faktura.objects.all().values('broj_fakture', 'datum_fakture', 'kupac__naziv_firme', 'neto_cijena', 'pdv', 'bruto_cijena', 'bruto_cijena_km', 'uplaceno', 'rok_placanja',  'razlika', 'placeno', 'kupac__drzava','ident_brojevi',).filter(datum_fakture__year=year)
    col = 0
    worksheet.set_column(0, 1, 28)
    worksheet.set_column(1, 1, 11)
    worksheet.set_column(2, 2, 50)
    worksheet.set_column(3, 10,12)
    for i in columns:
        worksheet.write(0, col, i)
        col += 1
    neto_cijena_evri = Faktura.objects.values('bruto_cijena','pdv', 'uplaceno', 'razlika', 'neto_cijena').filter(Q(kupac__drzava='Germany') | Q(kupac__drzava='Poland'), datum_fakture__year=year)
    neto = 0
    pdv = 0
    uplaceno = 0
    razlika = 0
    bruto = 0
    for n in neto_cijena_evri:
        for k in n:
            if k == 'uplaceno':
                uplaceno += n[k]
            elif k == 'neto_cijena':
                neto += n[k]
            elif k == 'pdv':
                pdv += n[k]

            elif k == 'razlika':
                razlika += n[k]
            elif k == 'bruto_cijena':
                bruto += n[k]
            else:
                pass

    neto_cijena_km = Faktura.objects.values('neto_cijena','bruto_cijena', 'pdv', 'uplaceno', 'razlika').filter(kupac__drzava='Bosna i Hercegovina', datum_fakture__year=year)
    neto_km = 0
    pdv_km = 0
    uplaceno_km = 0
    razlika_km = 0
    bruto_km = 0
    for n in neto_cijena_km:
        for k in n:
            if k == 'neto_cijena':
                neto_km += n[k]
            elif k == 'pdv':
                pdv_km += n[k]
            elif k == 'uplaceno':
                uplaceno_km += n[k]
            elif k == 'razlika':
                razlika_km += n[k]
            elif k == 'bruto_cijena':
                bruto_km += n[k]
            else:
                pass


    format1 = workbook.add_format({'num_format': 'd-m-yyyy'})
    format1.set_text_wrap()
    format1.set_align('vcenter')
    format1.set_align('center')
    format2 = workbook.add_format({'num_format': '#,##0.00 [$KM-sr-Latn-BA]', 'text_wrap': 1})
    format2.set_text_wrap()
    format2.set_align('vcenter')
    format2.set_align('right')
    format3 = workbook.add_format({'num_format': '#,##0.00 [$€-fr-FR]', 'text_wrap': 1})
    format3.set_text_wrap()
    format3.set_align('vcenter')
    format3.set_align('right')
    format4 = workbook.add_format({'num_format': '#,##0.00 [$KM-sr-Latn-BA]', 'text_wrap': 1})
    format4.set_text_wrap()
    format4.set_align('vcenter')
    format4.set_align('right')
    format4.set_bg_color('green')
    format5 = workbook.add_format({'num_format': '#,##0.00 [$€-fr-FR]', 'text_wrap': 1})
    format5.set_text_wrap()
    format5.set_align('vcenter')
    format5.set_align('right')
    format5.set_bg_color('blue')
    format4.set_color('white')
    format5.set_color('white')
    format6 = workbook.add_format()
    format6.set_text_wrap()
    format6.set_align('vcenter')
    format6.set_align('left')
    row_num1 = 0

    for dic in data:
        row_num1 += 1
        col_num1 = 0
        for key in dic:
            if key == 'datum_fakture':
                worksheet.write(row_num1, col_num1, dic[key], format1)

            elif key == 'neto_cijena':
                if dic['kupac__drzava'] == 'Bosna i Hercegovina':
                    worksheet.write(row_num1, col_num1, dic[key], format2)
                else:
                    worksheet.write(row_num1, col_num1, dic[key], format3)
            elif key == 'kupac__drzava':
                pass
            elif key == 'pdv':
                if dic['kupac__drzava'] == 'Bosna i Hercegovina':
                    worksheet.write(row_num1, col_num1, dic[key], format2)
                else:
                    worksheet.write(row_num1, col_num1, dic[key], format3)
            elif key == 'bruto_cijena':
                if dic['kupac__drzava'] == 'Bosna i Hercegovina':
                    worksheet.write(row_num1, col_num1, dic[key], format2)
                else:
                    worksheet.write(row_num1, col_num1, dic[key], format3)
            elif key == 'uplaceno':
                if dic['kupac__drzava'] == 'Bosna i Hercegovina':
                    worksheet.write(row_num1, col_num1, dic[key], format2)
                else:
                    worksheet.write(row_num1, col_num1, dic[key], format3)
            elif key == 'razlika':
                if dic['kupac__drzava'] == 'Bosna i Hercegovina':
                    worksheet.write(row_num1, col_num1, dic[key], format2)
                else:
                    worksheet.write(row_num1, col_num1, dic[key], format3)
            elif key == 'rok_placanja':
                worksheet.write(row_num1, col_num1, dic[key], format1)
            elif key == 'bruto_cijena_km':
                worksheet.write(row_num1, col_num1, dic[key], format2)
            elif key == 'broj_fakture':
                worksheet.write(row_num1, col_num1,  'IN-{}-{}-{}'.format(dic[key], dic['datum_fakture'].strftime('%Y%m%d'), dic['ident_brojevi']), format6)
            elif key == 'ident_brojevi':
                pass
            else:
                worksheet.write(row_num1, col_num1, dic[key])
            col_num1 += 1

    worksheet.write(row_num1+1,6, '=SUM(G2:G{})'.format(row_num1+1), format4)
    wrap_format = workbook.add_format()
    wrap_format.set_text_wrap()
    wrap_format.set_align('vcenter')
    wrap_format.set_align('center')
    worksheet.add_table('A1:K{}'.format(row_num1+2), {'columns':[
        {'header':'Broj fakture', 'header_format': wrap_format, 'total_string': 'Totals'},
        {'header':'Datum fakture', 'header_format': wrap_format},
        {'header':'Komitent', 'header_format': wrap_format},
        {'header': 'Iznos neto', 'header_format': wrap_format},
        {'header': 'PDV 17%', 'header_format': wrap_format},
        {'header': 'Ukupan iznos u Evrima', 'header_format': wrap_format},
        {'header': 'Ukupan iznos u KM', 'header_format': wrap_format},
        {'header': 'Uplaćeno', 'total_function': 'sum', 'header_format': wrap_format},
        {'header': 'Rok plaćanja', 'header_format': wrap_format},
        {'header': 'Razlika', 'total_function': 'sum', 'header_format': wrap_format},
        {'header': 'Realizovano', 'header_format': wrap_format},
    ]})
    worksheet.write(row_num1+1, 5, bruto, format5)
    worksheet.write(row_num1 + 2, 5, bruto_km, format4)
    worksheet.write(row_num1 + 1, 3, neto, format5)
    worksheet.write(row_num1 + 2, 3, neto_km, format4)
    worksheet.write(row_num1 + 1, 4, pdv, format5)
    worksheet.write(row_num1 + 2, 4, pdv_km, format4)
    worksheet.write(row_num1 + 1, 7, uplaceno, format5)
    worksheet.write(row_num1 + 2, 7, uplaceno_km, format4)
    worksheet.write(row_num1 + 1, 9, razlika, format5)
    worksheet.write(row_num1 + 2, 9, razlika_km, format4)
    workbook.close()


    output.seek(0)


    filename = 'Pregled faktura za {}.xlsx'.format(year)
    response = HttpResponse(output,content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename=%s' % filename

    return response

def ponuda_u_fakturu(request, pk):

    ponuda = Ponuda.objects.get(pk=pk)
    faktura = Faktura.objects.all().first()
    datum_fakture1 = faktura.datum_fakture + datetime.timedelta(days=1)
    f = int(faktura.broj_fakture) + 1
    broj_fakture1 = ''
    if f < 10:
        broj_fakture1 = '000'+str(f)
    elif f < 100:
        broj_fakture1 = '00'+str(f)
    elif f < 1000:
        broj_fakture1 = '0'+str(f)
    else:
        broj_fakture1 = str(f)

    kreiraj_fakturu = Faktura(broj_fakture=broj_fakture1, kupac_id=ponuda.kupac.pk, datum_fakture=datum_fakture1, ident_brojevi=ponuda.ident_brojevi)
    kreiraj_fakturu.save()

    prodaja = ProdajaPonuda.objects.all().filter(ponuda_id=pk)

    for data in prodaja:
        faktura_prodaja = Prodaja(faktura_id=kreiraj_fakturu.pk, opis_usluge=data.opis_usluge, kolicina=data.kolicina, pozicija_id=data.pozicija.pk)
        faktura_prodaja.save()

    return HttpResponseRedirect('/fakture/lista_faktura/{}'.format(kreiraj_fakturu.pk))

def ponuda_storno(request, pk):
    ponuda = Ponuda.objects.get(pk=pk)
    ponuda.placeno = 'Stornirano'
    ponuda.save()
    return HttpResponseRedirect('/fakture/lista_ponuda/{}'.format(ponuda.pk))