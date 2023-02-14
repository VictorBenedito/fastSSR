from django.shortcuts import render, redirect
from .forms import NameForm, LoginForm, UploadFileForm, DownloadForm
from .tables import PersonTable
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from .models import User, Project, ProjectData, DataStatistic
import pandas as pd
import os, re
import sys
import time

# Celery Task
from .tasks import ProcessDownload

def upload_file(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            handle_uploaded_file(request.FILES['file'])
            return HttpResponseRedirect('/success/url/')
        else:
            form = UploadFileForm()
    return render(request, 'index.html', {'form': form})

def index(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            # CRIAR O USER NO DB COM OS DADOS DO FORMULÁRIO
            user = User.objects.create(name=request.POST['name'], email=request.POST['email'])
            user.save()
            # ARMAZENA AS INFORMAÇÕES NA SESSÃO
            request.session['name'] = request.POST['name']  
            request.session['email'] = request.POST['email']
            # CRIAR O PROJETO NO DB
            project = Project.objects.create(user=user)
            project.save()
            request.session['project'] = project.pk
            request.session['statusProcessament'] = 'Iniciando...'
            request.session['step01'] = False
            request.session['step02'] = False
            request.session['step03'] = False
            request.session['percent03'] = 0

            # CRIAR PASTA DO PROJETO USER[PK]_PROJECT[PK]
            dirproject = f'USER{user.pk}_PROJECT{project.pk}'
            os.system(f'mkdir {dirproject}')

            # CRIAR SUBPASTAS DO PROJETO
            subdirectories = ['UserOutputs', 'UserData', 'UserData/FASTA', 'UserData/GBKs']
            for subdir in subdirectories:
                os.system(f'mkdir {dirproject}/{subdir}')

            # TRANSFERIR OS ARQUIVOS PARAS AS SUBPASTAS
            # |---FASTAs
            request.session['statusProcessament'] = "Upload dos Arquivos..."
            for f in request.FILES.getlist('fileFasta'):
                request.session['statusProcessament'] = f'Enviando arquivo {f}...'
                handle_uploaded_file(f, f'{dirproject}/{subdirectories[2]}')

            # |---GBKs
            for f in request.FILES.getlist('fileGBK'):
                request.session['statusProcessament'] = f'Enviando arquivo {f}...'
                handle_uploaded_file(f, f'{dirproject}/{subdirectories[3]}')

            
            print('================================================================')
            print('=                 Convertendo Arquivos GBKtoPTT                =')
            print('================================================================')
            request.session['statusProcessament'] = "Convertendo Arquivos GBKtoPTT..."
            os.system(f'python3 microssatelites/Scripts/GBKtoPTT.py {dirproject}')
            request.session['step01'] = True

            print('================================================================')
            print('=                       Executando o IMEx                      =')
            print('================================================================')
            request.session['statusProcessament'] = "Extraindo Microssatelites..."
            os.system(f'mkdir {dirproject}/{subdirectories[0]}/OutPutProcessed')
            os.system(f'python3 microssatelites/Scripts/IMEX.py {dirproject}')
            request.session['step02'] = True

            # os.system(f'mkdir {dirproject}/{subdirectories[0]}/OutPutProcessed')
            # os.system(f'cp -R IMEx_OUTPUT {dirproject}/{subdirectories[0]}/OutPutProcessed')

            print('================================================================')
            print('=                Processando Arquivos do IMEx                  =')
            print('================================================================')
            request.session['statusProcessament'] = "Extraindo Dados dos Microssatelites..."
            
            # Ler Pasta do IMEx_OUTPUT
            files = os.listdir(f'{dirproject}/UserOutputs/OutPutProcessed/IMEx_OUTPUT')
            if '.DS_Store' in files:
                files.remove('.DS_Store')
            cont = 1
            for i in files:
                path_file_summary = f'{dirproject}/UserOutputs/OutPutProcessed/IMEx_OUTPUT/'+ i +'/TEXT_OUTPUT/'+ i + '_summary.txt'
                path_file_aln = f'{dirproject}/UserOutputs/OutPutProcessed/IMEx_OUTPUT/'+ i +'/TEXT_OUTPUT/'+ i + '_aln.txt'
                # Extrair Dados do Summary
                print('Extraindo dados do Arquivo Summary')
                extractSummary(path_file_summary, project)
                if os.path.exists(path_file_aln):
                    print(f'Lendo arquivo {cont} de {len(files)}')
                    # path_file_out = 'UserOutputs/OutPutProcessed/'
                    # os.system('python3 microssatelites/Scripts/newRead.py ' + path_file_aln + ' ' + str(project.pk))
                    doc2db(path_file_aln, project)
                    request.session['percent03'] = round(cont/len(files) * 100, 1)
                else:
                    print('Arquivo de Entrada não encontrado!')
                cont+=1

                # if os.path.exists(f'{dirproject}/UserOutputs/OutPutProcessed'):
                #     path_file_out = f'{dirproject}/UserOutputs/OutPutProcessed/'
                #     os.system('python3 microssatelites/Scripts/read.py ' + path_file + ' > '+ path_file_out + i +'.txt')
            request.session['statusProcessament'] = "Finalizando..."
            request.session['step03'] = True
            print('================================================================')
            print('=                  Dados para os Graficos                      =')
            print('================================================================')
            dataStatistics = DataStatistic.objects.filter(project=project)
            projectdata = ProjectData.get_data(project.pk)
            totalDataStatistic = DataStatistic.get_total_data_statistic(project.pk)
            motifs = ProjectData.get_motifs(project.pk)
            lista = []
            listaCepas = []
            listaCepasTotais = []
            for i in motifs:
                lista.append(i)
                listaCepas.append(ProjectData.get_cepas(i[0], project.pk, i[2]))

            for list in listaCepas:
                for l in list:
                    if l[1] not in listaCepasTotais:
                        listaCepasTotais.append(l[1])
            motifs2 = ProjectData.get_motifs2(project.pk)
            lista2 = []
            listaCepas2 = []
            listaCepasTotais2 = []
            for j in motifs2:
                lista2.append(j)
                listaCepas2.append(ProjectData.get_cepas2(j[0], project.pk))
            
            for list2 in listaCepas2:
                for l2 in list2:
                    if l2[1] not in listaCepasTotais2:
                        listaCepasTotais2.append(l2[1])
            return render(request,'result.html', {'user': user, 'project': project, 'dataStatistics': dataStatistics, 'projectdata': projectdata, 'totalDataStatistic': totalDataStatistic, 'lista':lista, 'lista2':lista2, 'listaCepas':listaCepas, 'listaCepas2': listaCepas2, 'listaCepasTotais':listaCepasTotais, 'listaCepasTotais2':listaCepasTotais2})
    else:
        form = UploadFileForm()
    return render(request, 'index.html', {'form': form})

# FUNÇÕES ACESSÓRIAS
@csrf_exempt
def handle_uploaded_file(f, directory):
    destination = open(f'{directory}/{f}', 'wb+')
    for chunk in f.chunks():
        destination.write(chunk)
    destination.close()
    return JsonResponse({'status': 'success'})

def get_processing_status(request):
  # Insira aqui o código para obter o status do processamento atual
    project = request.session.get('project', '')
    if project == '':
        request.session['step01'] = False
        request.session['step02'] = False
        request.session['step03'] = False
        request.session['percent03'] = 0
        data = {
            'statusProcessament': 'Iniciando...',
            'step01' : request.session['step01'],
            'step02' : request.session['step02'],
            'step03' : request.session['step03'],
            'percent03' : request.session['percent03']
        }
    else:    
        data = {
            'statusProcessament': request.session['statusProcessament'],
            'step01' : request.session['step01'],
            'step02' : request.session['step02'],
            'step03' : request.session['step03'],
            'percent03' : request.session['percent03']
        }
    # if request.method == 'GET':
    #     get = request.GET

        # try:
        #     if 'project' in get:
        #         # Retornar o status do processamento como resposta JSON
        #         data = {
        #             'haveProject': True,
        #             'project': dic[get['project']],
        #             'statusProcessament': dic[get['project']]['statusProcessament'],
        #             'step01': dic[get['project']]['step01'],
        #             'step02': dic[get['project']]['step02'],
        #             'step03': dic[get['project']]['step03'],
        #             'precent_complete': dic[get['project']]['percent03'],
        #         }
        #     else:  
        #         if lastProject != None:
        #             data = {
        #                 'haveProject': False,
        #                 'statusProcessament': 'Iniciando...',
        #                 'step01': False,
        #                 'step02': False,
        #                 'step03': False,
        #                 'precent_complete': 0,
        #                 'project': lastProject
        #             }
        #         else:
        #             data = {
        #                 'haveProject': False,
        #                 'statusProcessament': 'Buscando Projeto...',
        #                 'step01': False,
        #                 'step02': False,
        #                 'step03': False,
        #                 'precent_complete': 0,
        #                 'project': False
        #             }
        # except KeyError as err:
        #     data = {
        #             'haveProject': False,
        #             'statusProcessament': 'ERRO! Projecto não existe!',
        #             'step01': False,
        #             'step02': False,
        #             'step03': False,
        #             'precent_complete': 0
        #         }


    return JsonResponse(data)

def dadosGrafico(request):
    projectdata = ProjectData.get_motifs(57)
    lista = []
    listaCepas = []
    listaCepasTotais = []
    for i in projectdata:
        lista.append(i)
        listaCepas.append(ProjectData.get_cepas(i[0], 57))

    for list in listaCepas:
        for l in list:
            if l[1] not in listaCepasTotais:
                listaCepasTotais.append(l[1])
    print(listaCepasTotais)
    
    context = {
        'lista': lista,
        'listaCepas': listaCepas,
        'listaCepasTotais': listaCepasTotais
    }
    return render(request,'datateste.html', context)

def extractSummary(file, project):
    perfeitos = 0
    imperfeitos = 0
    codificante = 0
    naoCodificante = 0
    perfCoding = 0
    perfNonCoding = 0
    impCoding = 0
    impNonCoding = 0

    perfMono = 0
    perfDi = 0
    perfTri = 0
    perfTetra = 0
    perfPenta = 0
    perfHexa = 0
    impMono = 0
    impDi = 0
    impTri = 0
    impTetra = 0
    impPenta = 0
    impHexa = 0

    with open(file, 'r') as arquivo:
        linhas = arquivo.readlines()
    #Count do total de SSR (-2 para desconsiderar as duas primeiras linhas, cabeçalho e divisor)
    totalSSR = len(linhas)-2

    # Percorre as linhas do arquivo
    for linha in linhas:
        # Desconsidera as linhas 1 e 2
        
        if not((linha == linhas[0]) or (linha == linhas[1])):
            # Separa as colunas baseado no espaço em branco entre elas
            linhaIndex = linha.split()

            # Consulta a coluna 6
            if int(linhaIndex[5]) == 0:
                # Perfeitos
                perfeitos += 1

                if len(linhaIndex[0]) == 1:
                    perfMono += 1

                if len(linhaIndex[0]) == 2:
                    perfDi += 1

                if len(linhaIndex[0]) == 3:
                    perfTri += 1

                if len(linhaIndex[0]) == 4:
                    perfTetra += 1

                if len(linhaIndex[0]) == 5:
                    perfPenta += 1

                if len(linhaIndex[0]) == 6:
                    perfHexa += 1

                if "Coding" in linhaIndex:
                    perfCoding += 1
                else:
                    perfNonCoding += 1
            else:
                # Imperfeitos
                imperfeitos += 1

                if len(linhaIndex[0]) == 1:
                    impMono += 1

                if len(linhaIndex[0]) == 2:
                    impDi += 1

                if len(linhaIndex[0]) == 3:
                    impTri += 1

                if len(linhaIndex[0]) == 4:
                    impTetra += 1

                if len(linhaIndex[0]) == 5:
                    impPenta += 1

                if len(linhaIndex[0]) == 6:
                    impHexa += 1

                if "Coding" in linhaIndex:
                    impCoding += 1
                else:
                    impNonCoding += 1
        codificante = perfCoding + impCoding
        naoCodificante = perfNonCoding + impNonCoding
        cepa = file.split("/")[-1].replace('_summary.txt',"")

    # data = {'Total SSR': totalSSR,
    # 'Total Codificante': codificante,
    # 'Total não Codificante': naoCodificante,
    # 'Mono': perfMono + impMono,
    # 'Di': perfDi + impDi,
    # 'Tri': perfTri + impTri,
    # 'Tetra': perfTetra + impTetra,
    # 'Penta': perfPenta + impPenta,
    # 'Hexa': perfHexa + impHexa,
    # 'Total Perfeitos': perfeitos,
    # 'Total Perfeitos Codificantes': perfCoding,
    # 'Total Perfeitos não Codificantes': perfNonCoding,
    # 'Perfeito Mono': perfMono,
    # 'Perfeito Di': perfDi,
    # 'Perfeito Tri': perfTri,
    # 'Perfeito Tetra': perfTetra,
    # 'Perfeito Penta': perfPenta,
    # 'Perfeito Hexa': perfHexa,
    # 'Total Imperfeitos': imperfeitos,
    # 'Total Imperfeitos Codificantes': impCoding,
    # 'Total Imperfeitos não Codificantes': impNonCoding,
    # 'Imperfeito Mono': impMono,
    # 'Imperfeito Di': impDi,
    # 'Imperfeito Tri': impTri,
    # 'Imperfeito Tetra': impTetra,
    # 'Imperfeito Penta': impPenta,
    # 'Imperfeito Hexa': impHexa}

    dataStatistic = DataStatistic.objects.create(
               cepa = cepa,
               totalSSR = totalSSR,
               totalCodificante = codificante,
               totalNaoCodificante = naoCodificante,
               mono = perfMono + impMono,
               di = perfDi + impDi,
               tri = perfTri + impTri,
               tetra = perfTetra + impTetra,
               penta = perfPenta + impPenta,
               hexa = perfHexa + impHexa,
               totalPerfeitos = perfeitos,
               totalPerfeitosCodificantes = perfCoding,
               totalPerfeitosNaoCodificantes = perfNonCoding,
               perfeitoMono = perfMono,
               perfeitoDi = perfDi,
               perfeitoTri = perfTri,
               perfeitoTetra = perfTetra,
               perfeitoPenta = perfPenta,
               perfeitoHexa = perfHexa,
               totalImperfeitos = imperfeitos,
               totalImperfeitosCodificantes = impCoding,
               totalImperfeitosNaoCodificantes = impNonCoding,
               imperfeitoMono = impMono,
               imperfeitoDi = impDi,
               imperfeitoTri = impTri,
               imperfeitoTetra = impTetra,
               imperfeitoPenta = impPenta,
               imperfeitoHexa = impHexa,
               project = project
    )
    dataStatistic.save()
    return dataStatistic

def doc2db(request, path, project):
    arquivo = open(path, 'r')
    linhas = arquivo.readlines()
    cont = 0

    objetos = []
    repeatMotif = ''
    lflanking = ''
    rflanking = ''
    consensus = ''
    iterations = ''
    tractLength = ''
    repeatMotifList = []
    motif = []
    cepa = path.split("/")[-1].replace('_aln.txt',"")

    # Ler o arquivo aln e extrai as informações dele
    for line in linhas:
        if(line.startswith('Consensus:')):
            repeatMotif = line.split(':')[1].replace("\n","")
            # repeatMotifList.append(repeatMotif)
            # print ('Repeat motif: ', line.split(':')[1])
        if(line.startswith('Start:')):
            match = re.findall(r'\d+', line)
            pos_start = int(match[0])
            pos_end = int(match[1])
            iterations = int(match[2])

        if(line.startswith('Total Imperfections:')):
            tractLength = line.split()[-1].replace("\n","")
            # print(line.split()[-1])
        if(line.startswith('Left Flanking Sequence:')):
            lflanking = linhas[cont+1].replace("\n","")
            consensus = linhas[cont+3].replace("\n","")
            # print('Left Flanking Sequence: ',linhas[cont+1])
        if(line.startswith('Right Flanking Sequence:')):
            rflanking = linhas[cont+1].replace("\n","")
            motif = [
                        { 'repeat': repeatMotif,
                          'iterations': iterations,
                          'tractLength': tractLength,
                          'lflanking': lflanking,
                          'consensus': consensus,
                          'rflanking': rflanking,
                        }
                    ]
            repeatMotifList.append(motif)
            projectdata = ProjectData.objects.create(cepa = cepa, motif = repeatMotif, lflanking = lflanking ,  rflanking = rflanking , iterations = iterations, tractlength = tractLength,  consensus = consensus, pos_start = pos_start, pos_end = pos_end, project = project)
            request.session['statusProcessament'] = f'Gravando Linha no Banco {cont} de {len(linhas)}'
            projectdata.save()
            
            # cursor.execute(f"INSERT INTO DATA (MOTIF, LFLANK, RFLANK, ITERATIONS, TRACKLENGTH, CONSENSUS, CONSULTA, CEPA) VALUES ('{repeatMotif}', ' {lflanking} ', ' {rflanking} ', {iterations}, {tractLength}, '{ consensus}', {1}, '{cepa}');")
        # objetos.append(File(cepa, repeatMotifList))
        cont += 1
    arquivo.close()

    print("Done.")

def result(request):
    if request.method == 'POST':
        context = {
            'projectdata' : request.POST['projectdata'],
            'dataStatistics': request.POST['dataStatistics'],
            'totalDataStatistic': request.POST['totalDataStatistic'],
            'lista': request.POST['lista'],
            'listaCepas': request.POST['listaCepas'],
            'listaCepasTotais': request.POST['listaCepasTotais']
            }
    else:
        dataStatistics = DataStatistic.objects.filter(project=57)
        totalDataStatistic = DataStatistic.get_total_data_statistic(57)
        projectdata = ProjectData.get_data(57)
        motifs = ProjectData.get_motifs(57)
        lista = []
        listaCepas = []
        listaCepasTotais = []
        for i in motifs:
            lista.append(i)
            listaCepas.append(ProjectData.get_cepas(i[0], 57, i[2]))

        for list in listaCepas:
            for l in list:
                if l[1] not in listaCepasTotais:
                    listaCepasTotais.append(l[1])
        
        motifs2 = ProjectData.get_motifs2(57)
        lista2 = []
        listaCepas2 = []
        listaCepasTotais2 = []
        for j in motifs2:
            lista2.append(j)
            listaCepas2.append(ProjectData.get_cepas2(j[0], 57))
        
        for list2 in listaCepas2:
            for l2 in list2:
                if l2[1] not in listaCepasTotais2:
                    listaCepasTotais2.append(l2[1])
        context = {
            'projectdata' : projectdata,
            'dataStatistics': dataStatistics,
            'totalDataStatistic': totalDataStatistic,
            'lista': lista,
            'listaCepas': listaCepas,
            'listaCepasTotais': listaCepasTotais,
            'lista2': lista2,
            'listaCepas2': listaCepas2,
            'listaCepasTotais2': listaCepasTotais2,
            }
    return render(request,'result.html', context)

def viewgen(request):
    return render(request, 'viewgen.html')

