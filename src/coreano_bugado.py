def coreano_para_grf(texto_coreano):
    """
    Converte texto coreano para o formato 'bugado' que aparece em arquivos GRF.
    """
    return texto_coreano.encode('euc-kr').decode('latin-1')

def grf_para_coreano(texto_bugado):
    """
    Converte texto 'bugado' de GRF de volta para coreano.
    """
    return texto_bugado.encode('latin-1').decode('euc-kr')


# 🔥 Exemplos de uso:
coreano = "러프윈드"
coreano1 = "강철"
coreano2 = "오리데오콘원석"
coreano3 = "프로펠라"
coreano4 = "다마스커스_"
coreano5 = "옐로우라이브"
coreano6 = "에르늄원석"
coreano7 = "초록색보석"
coreano8 = "빨간허브"


coreano11 = "매우단단한껍질"
coreano12 = "자르곤"
coreano13 = "사마귀의팔"
coreano14 = "셀"
coreano15 = "매우단단한껍질"

print(f"{coreano_para_grf(coreano)}")
print(f"{coreano_para_grf(coreano1)}")
print(f"{coreano_para_grf(coreano2)}")
print(f"{coreano_para_grf(coreano3)}")
print(f"{coreano_para_grf(coreano4)}")
print(f"{coreano_para_grf(coreano5)}")
print(f"{coreano_para_grf(coreano6)}")
print(f"{coreano_para_grf(coreano7)}")
print(f"{coreano_para_grf(coreano8)}")
print(f"{coreano_para_grf(coreano11)}")
print(f"{coreano_para_grf(coreano12)}")
print(f"{coreano_para_grf(coreano13)}")
print(f"{coreano_para_grf(coreano14)}")
print(f"{coreano_para_grf(coreano15)}")