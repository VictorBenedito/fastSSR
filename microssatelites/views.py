from django.shortcuts import render, redirect
from .forms import NameForm, LoginForm, UploadFileForm, DownloadForm
from .tables import PersonTable
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.shortcuts import render
from django.contrib.auth import authenticate, login
from django.views.decorators.csrf import csrf_exempt
import pandas as pd
import os
import time
from django.db.models import Count
from .models import User, Project, ProjectData, DataStatistic, Person
# Celery Task
from .tasks import ProcessDownload

# Create your views here.

def upload(request):
    return render(request, 'progressbar.html')

# def handle_upload(request):
#     if request.method == 'POST':
#         file = request.FILES['file']
#         # process the file, e.g. save it to the server
#         dirproject = f'USER_PROJECT'
#         os.system(f'mkdir {dirproject}')
#         handle_uploaded_file(file, dirproject)

#         return JsonResponse({'status': 'success'})

def handle_upload(request):
    if request.method == 'POST':
        files = request.FILES.getlist('file')
        # for file in files:
            # process the file, e.g. save it to the server
            # ...
        return JsonResponse({'status': 'success'})

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
            print('Entrou no FORM')
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
            os.system(f'python3 microssatelites/Scripts/GBKtoPTT.py {dirproject}')

            print('================================================================')
            print('=                       Executando o IMEx                      =')
            print('================================================================')
            os.system(f'mkdir {dirproject}/{subdirectories[0]}/OutPutProcessed')
            os.system(f'python3 microssatelites/Scripts/IMEX.py {dirproject}')
            # os.system(f'mkdir {dirproject}/{subdirectories[0]}/OutPutProcessed')
            # os.system(f'cp -R IMEx_OUTPUT {dirproject}/{subdirectories[0]}/OutPutProcessed')

            print('================================================================')
            print('=                Processando Arquivos do IMEx                  =')
            print('================================================================')

            # Abrir Pasta do IMEx_OUTPUT
            files = os.listdir(f'{dirproject}/UserOutputs/OutPutProcessed/IMEx_OUTPUT')
            if '.DS_Store' in files:
                files.remove('.DS_Store')

            for i in files:
                path_file_summary = f'{dirproject}/UserOutputs/OutPutProcessed/IMEx_OUTPUT/'+ i +'/TEXT_OUTPUT/'+ i + '_summary.txt'
                path_file_aln = f'{dirproject}/UserOutputs/OutPutProcessed/IMEx_OUTPUT/'+ i +'/TEXT_OUTPUT/'+ i + '_aln.txt'
                cont = 1
                # Extrair Dados do Summary
                print('Extraindo dados do Arquivo Summary')
                extractSummary(path_file_summary, project)
                if os.path.exists(path_file_aln):
                    print(f'Lendo arquivo {cont} de {len(files)}')
                    # path_file_out = 'UserOutputs/OutPutProcessed/'
                    # os.system('python3 microssatelites/Scripts/newRead.py ' + path_file_aln + ' ' + str(project.pk))
                    doc2db(path_file_aln, project)
                else:
                    print('Arquivo de Entrada não encontrado!')
                cont+=1

                # if os.path.exists(f'{dirproject}/UserOutputs/OutPutProcessed'):
                #     path_file_out = f'{dirproject}/UserOutputs/OutPutProcessed/'
                #     os.system('python3 microssatelites/Scripts/read.py ' + path_file + ' > '+ path_file_out + i +'.txt')

            print('================================================================')
            print('=                      Criando Tabela 01                       =')
            print('================================================================')
            # os.system(f'python3 microssatelites/Scripts/createTable.py --input {dirproject}/UserOutputs/OutPutProcessed/ --output_file {dirproject}/UserOutputs/Microsat')

            print('================================================================')
            print('=                      Dados para o DB                         =')
            print('================================================================')
            dataStatistics = DataStatistic.objects.filter(project=project)
            projectdata = ProjectData.get_data(project.pk)
            totalDataStatistic = DataStatistic.get_total_data_statistic(project.pk)
            return render(request,'result.html', {'user': user, 'project': project, 'dataStatistics': dataStatistics, 'projectdata': projectdata, 'totalDataStatistic': totalDataStatistic})
    else:
        form = UploadFileForm()
    return render(request, 'index.html', {'form': form})

def person_list(request):
    # table = PersonTable(ProjectData.objects.all())
    table = PersonTable(ProjectData.objects.values('motif','cepa','iterations', 'consensus', 'lflanking', 'rflanking').annotate(dcount=Count('motif')).order_by())
    table.paginate(page=request.GET.get("page", 1), per_page=25)

    return render(request, "person_list.html", {
        "table": table
    })

# FUNÇÕES ACESSÓRIAS
@csrf_exempt
def handle_uploaded_file(f, directory):
    destination = open(f'{directory}/{f}', 'wb+')
    for chunk in f.chunks():
        destination.write(chunk)
    destination.close()
    return JsonResponse({'status': 'success'})

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
            'dataStatistics': request.POST['redataStatistics'],
            'totalDataStatistic': request.POST['totalDataStatistic']
            }
    else:
        context = {
            'projectdata' : [1,2,3,4,5,6],
            'dataStatistics': None,
            'totalDataStatistic': None
            }
    return render(request,'result.html', context)
    # if request.method == 'GET':
    #     print('Entrou no POST')
    #     # user = User.objects.filter(id=request.POST['project'])[0]
    #     # project = Project.objects.filter(user=user)[0]
    #     user = request.POST['user']
    #     project = request.POST['project']
    #     dataStatistics = DataStatistic.objects.filter(project=project)
    #     totalDataStatistic = DataStatistic.get_total_data_statistic(project.pk)
    #     print(project)
    #     projectdata = ProjectData.get_data(project.pk)
    #     context = {
    #         'projectdata' : projectdata,
    #         'dataStatistics': dataStatistics,
    #         'totalDataStatistic': totalDataStatistic
    #     }
    #     return render(request,'result.html', context)
    # else:
    #     user = User.objects.filter(id=8)[0]
    #     project = Project.objects.filter(user=user)[0]
    #     dataStatistics = DataStatistic.objects.filter(project=project)
    #     totalDataStatistic = DataStatistic.get_total_data_statistic(project.pk)
    #     print(project)
    #     projectdata = ProjectData.get_data(project.pk)
    #     context = {
    #         'projectdata' : projectdata,
    #         'dataStatistics': dataStatistics,
    #         'totalDataStatistic': totalDataStatistic
    #     }

    # return render(request,'result.html', context)
