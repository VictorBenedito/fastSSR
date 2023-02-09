from django.shortcuts import render, redirect
from .forms import NameForm, LoginForm, UploadFileForm, DownloadForm
from .tables import PersonTable
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from .models import User, Project, ProjectData, DataStatistic, Person
import pandas as pd
import os
import time
# Celery Task
from .tasks import ProcessDownload

statusProcessament = ""
step01 = False
step02 = False
step03 = False
percent03 = 0



is_complete = False

def upload(request):
    return render(request, 'progressbar.html')

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
            global statusProcessament
            global step01
            global step02
            global step03
            global percent03


            # CRIAR O USER NO DB COM OS DADOS DO FORMULÁRIO
            user = User.objects.create(name=request.POST['name'], email=request.POST['email'])
            user.save()

            # CRIAR O PROJETO NO DB
            project = Project.objects.create(user=user)
            project.save()

            # CRIAR PASTA DO PROJETO USER[PK]_PROJECT[PK]
            dirproject = f'USER{user.pk}_PROJECT{project.pk}'
            os.system(f'mkdir {dirproject}')

            # CRIAR SUBPASTAS DO PROJETO
            subdirectories = ['UserOutputs', 'UserData', 'UserData/FASTA', 'UserData/GBKs']
            for subdir in subdirectories:
                os.system(f'mkdir {dirproject}/{subdir}')

            # TRANSFERIR OS ARQUIVOS PARAS AS SUBPASTAS
            # |---FASTAs
            for f in request.FILES.getlist('fileFasta'):
                handle_uploaded_file(f, f'{dirproject}/{subdirectories[2]}')

            # |---GBKs
            for f in request.FILES.getlist('fileGBK'):
                handle_uploaded_file(f, f'{dirproject}/{subdirectories[3]}')

            
            print('================================================================')
            print('=                 Convertendo Arquivos GBKtoPTT                =')
            print('================================================================')
            statusProcessament = "Convertendo Arquivos GBKtoPTT..."
            os.system(f'python3 microssatelites/Scripts/GBKtoPTT.py {dirproject}')
            step01 = True
            

            print('================================================================')
            print('=                       Executando o IMEx                      =')
            print('================================================================')
            statusProcessament = "Extraindo Microssatelites..."
            os.system(f'mkdir {dirproject}/{subdirectories[0]}/OutPutProcessed')
            os.system(f'python3 microssatelites/Scripts/IMEX.py {dirproject}')
            step02 = True

            # os.system(f'mkdir {dirproject}/{subdirectories[0]}/OutPutProcessed')
            # os.system(f'cp -R IMEx_OUTPUT {dirproject}/{subdirectories[0]}/OutPutProcessed')

            print('================================================================')
            print('=                Processando Arquivos do IMEx                  =')
            print('================================================================')
            statusProcessament = "Extraindo Dados..."
            
            # Abrir Pasta do IMEx_OUTPUT
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
                    percent03 = cont/len(files) * 100
                    print (percent03)
                else:
                    print('Arquivo de Entrada não encontrado!')
                cont+=1

                # if os.path.exists(f'{dirproject}/UserOutputs/OutPutProcessed'):
                #     path_file_out = f'{dirproject}/UserOutputs/OutPutProcessed/'
                #     os.system('python3 microssatelites/Scripts/read.py ' + path_file + ' > '+ path_file_out + i +'.txt')
            step03 = True
            statusProcessament = "Finalizando..."
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
                listaCepas.append(ProjectData.get_cepas(i[0], project.pk))

            for list in listaCepas:
                for l in list:
                    if l[1] not in listaCepasTotais:
                        listaCepasTotais.append(l[1])
            return render(request,'result.html', {'user': user, 'project': project, 'dataStatistics': dataStatistics, 'projectdata': projectdata, 'totalDataStatistic': totalDataStatistic, 'lista':lista, 'listaCepas':listaCepas, 'listaCepasTotais':listaCepasTotais})
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

  # Retornar o status do processamento como resposta JSON
  data = {
    'statusProcessament': statusProcessament,
    'percent_complete': percent03,
    'step01': step01,
    'step02': step02,
    'step03': step03,
    'is_complete': is_complete
  }
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

def doc2db(path, project):
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
            iterations = line.split()[-1].replace("\n","")

            # print(line.split()[-1])
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
            projectdata = ProjectData.objects.create(cepa = cepa, motif = repeatMotif, lflanking = lflanking ,  rflanking = rflanking , iterations = iterations, tractlength = tractLength,  consensus = consensus, project = project)
            global statusProcessament
            statusProcessament = f'Gravando Linha no Banco {cont} de {len(linhas)}'
            projectdata.save()
            
            # cursor.execute(f"INSERT INTO DATA (MOTIF, LFLANK, RFLANK, ITERATIONS, TRACKLENGTH, CONSENSUS, CONSULTA, CEPA) VALUES ('{repeatMotif}', ' {lflanking} ', ' {rflanking} ', {iterations}, {tractLength}, '{ consensus}', {1}, '{cepa}');")
        # objetos.append(File(cepa, repeatMotifList))
        cont += 1
    arquivo.close()

    # Cleanup Database
    # conn.commit()
    # cursor.close()
    # conn.close()
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
        dataStatistics = DataStatistic.objects.filter(project=73)
        totalDataStatistic = DataStatistic.get_total_data_statistic(73)
        projectdata = ProjectData.get_data(73)
        motifs = ProjectData.get_motifs(73)
        lista = []
        listaCepas = []
        listaCepasTotais = []
        for i in motifs:
            lista.append(i)
            listaCepas.append(ProjectData.get_cepas(i[0], 73))

        for list in listaCepas:
            for l in list:
                if l[1] not in listaCepasTotais:
                    listaCepasTotais.append(l[1])

        context = {
            'projectdata' : projectdata,
            'dataStatistics': dataStatistics,
            'totalDataStatistic': totalDataStatistic,
            'lista': lista,
            'listaCepas': listaCepas,
            'listaCepasTotais': listaCepasTotais
            }
    return render(request,'result.html', context)
