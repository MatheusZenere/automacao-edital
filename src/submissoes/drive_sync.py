"""Utilitários para sincronização, download e ingestão de pastas do Google Drive.
Permite que qualquer professor ou usuário conecte o seu próprio Google Drive através de:
1. Link público ou compartilhado do Google Drive (download automático via gdown).
2. Upload direto do arquivo ZIP baixado da pasta do Google Drive.
"""
import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import re
import shutil
import tarfile
import threading
from dataclasses import dataclass
from urllib.parse import urlsplit
import zipfile

try:
    import gdown
except ImportError:
    gdown = None

try:
    import requests
except ImportError:
    requests = None


# Limites de segurança contra arquivos maliciosos ou pastas gigantes (disco/memória)
MAX_TOTAL_DESCOMPACTADO = 1024 * 1024 * 1024  # 1 GB descompactado (anti zip-bomb)
MAX_ARQUIVOS = 2000
MAX_BYTES_ARQUIVO_DRIVE = 100 * 1024 * 1024  # 100 MB por arquivo baixado do Drive


class ErroDrivePersonalizado(Exception):
    """Exceção base com mensagem amigável em português para o usuário."""
    pass


def extrair_id_drive(link_ou_id: str) -> str:
    """Extrai o ID da pasta a partir de um link do Google Drive ou retorna o próprio ID."""
    texto = link_ou_id.strip()
    if not texto:
        return ""

    m = re.search(r"folders/([a-zA-Z0-9_-]+)", texto)
    if m:
        return m.group(1)

    m2 = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", texto)
    if m2:
        return m2.group(1)

    # Caso o usuário já tenha colado o ID direto (ex: 1wBpMN-6MAl7OhtJd9hwPwM5ktaCVvuQH)
    if re.match(r"^[a-zA-Z0-9_-]{15,}$", texto):
        return texto

    return ""


def detectar_raiz_submissoes(pasta: Path) -> Path:
    """Encontra a pasta que contém diretamente as subpastas dos projetos (PVG...),
    mesmo que o ZIP ou Drive venha envolvido em uma subpasta raiz.
    """
    if not pasta.exists():
        return pasta

    subpastas = [d for d in pasta.iterdir() if d.is_dir() and not d.name.startswith(".")]
    arquivos_soltos = [f for f in pasta.iterdir() if f.is_file() and not f.name.startswith(".")]

    # Desce só por uma pasta "embrulho": nada solto aqui e uma única subpasta que, por sua vez,
    # tem subpastas. Assim a raiz com o edital solto + PVG.../ é mantida, e uma pasta com um
    # único projeto (só arquivos dentro) não é confundida com embrulho.
    if len(subpastas) == 1 and not arquivos_soltos:
        unica = subpastas[0]
        if any(d.is_dir() and not d.name.startswith(".") for d in unica.iterdir()):
            return detectar_raiz_submissoes(unica)

    return pasta


def _checar_limites(qtd_arquivos: int, total_bytes: int) -> None:
    if qtd_arquivos > MAX_ARQUIVOS or total_bytes > MAX_TOTAL_DESCOMPACTADO:
        raise ErroDrivePersonalizado(
            "O arquivo compactado é grande demais para ser processado "
            f"(limite: {MAX_ARQUIVOS} arquivos e {MAX_TOTAL_DESCOMPACTADO // 2**20} MB descompactado). "
            "Envie apenas a pasta com os editais e anexos."
        )


def extrair_zip_submissoes(conteudo_zip: bytes, pasta_destino: Path, nome_arquivo: str = "") -> Path:
    """Valida e descompacta um arquivo compactado (ZIP) em uma pasta local.
    Rejeita estritamente qualquer arquivo que não seja compactado.
    """
    if not conteudo_zip:
        raise ErroDrivePersonalizado("O arquivo compactado enviado está vazio (0 bytes).")

    if nome_arquivo and not nome_arquivo.lower().endswith((".zip", ".tar.gz", ".tar", ".tgz")):
        extensao = Path(nome_arquivo).suffix or "desconhecida"
        raise ErroDrivePersonalizado(
            f"Formato não permitido ({extensao})! O sistema aceita exclusivamente arquivos compactados (.zip). "
            "Não é permitido o envio de PDFs ou outros formatos soltos. "
            "Por favor, compacte a pasta contendo as submissões ou faça o download da pasta como .zip no Google Drive."
        )

    # Validação do cabeçalho binário de arquivo compactado (ZIP ou TAR)
    is_zip = zipfile.is_zipfile(io.BytesIO(conteudo_zip))
    is_tar = False
    try:
        is_tar = tarfile.is_tarfile(io.BytesIO(conteudo_zip))
    except Exception:
        pass

    if not is_zip and not is_tar:
        raise ErroDrivePersonalizado(
            "O arquivo enviado não é um arquivo compactado válido. "
            "O sistema aceita estritamente arquivos compactados (.zip). "
            "Certifique-se de baixar a pasta completa pelo Google Drive (botão direito > 'Fazer download')."
        )

    try:
        if pasta_destino.exists():
            shutil.rmtree(pasta_destino)
        pasta_destino.mkdir(parents=True, exist_ok=True)

        if is_zip:
            with zipfile.ZipFile(io.BytesIO(conteudo_zip), "r") as z:
                infos = z.infolist()
                _checar_limites(len(infos), sum(i.file_size for i in infos))
                z.extractall(pasta_destino)
        elif is_tar:
            with tarfile.open(fileobj=io.BytesIO(conteudo_zip), mode="r:*") as t:
                membros = t.getmembers()
                _checar_limites(len(membros), sum(m.size for m in membros))
                # filter="data" bloqueia caminhos absolutos, ".." e links para fora do destino
                t.extractall(pasta_destino, filter="data")
    except ErroDrivePersonalizado:
        shutil.rmtree(pasta_destino, ignore_errors=True)
        raise
    except Exception as e:
        raise ErroDrivePersonalizado(
            "Não conseguimos abrir o arquivo .zip. Ele pode estar corrompido ou incompleto. "
            "Tente baixar a pasta novamente pelo Google Drive e enviar o novo arquivo."
        ) from e

    pasta_raiz = detectar_raiz_submissoes(pasta_destino)

    # Verifica se realmente há arquivos
    arquivos_encontrados = list(pasta_raiz.glob("**/*.*"))
    if not arquivos_encontrados:
        raise ErroDrivePersonalizado(
            "O arquivo compactado foi descompactado com sucesso, mas não contém documentos. "
            "Verifique se você compactou a pasta correta com os editais e anexos."
        )

    return pasta_raiz


DICA_ZIP = (
    "Se preferir, baixe a pasta pelo próprio Google Drive (clique com o botão direito na pasta > "
    "'Fazer download') e envie o arquivo gerado pela opção 'Upload de ZIP do Drive'."
)


def _traduzir_erro_drive(erro: Exception) -> str:
    """Converte erros técnicos do download em mensagens simples para qualquer usuário."""
    msg = f"{type(erro).__name__} {erro}".lower()

    if any(t in msg for t in ("permission", "cannot retrieve", "access denied", "forbidden", "403", "private")):
        return (
            "Não conseguimos abrir essa pasta porque ela não está compartilhada publicamente. "
            "No Google Drive, clique com o botão direito na pasta > 'Compartilhar' > em 'Acesso geral' "
            "escolha 'Qualquer pessoa com o link' e tente novamente."
        )
    if any(t in msg for t in ("404", "not found", "no such")):
        return (
            "Não encontramos essa pasta no Google Drive. Confira se o link foi copiado por completo "
            "e se a pasta não foi apagada ou movida."
        )
    if any(t in msg for t in ("quota", "too many", "rate limit", "429")):
        return (
            "O Google Drive está recebendo muitos pedidos de download dessa pasta agora e bloqueou "
            "temporariamente. Aguarde alguns minutos e tente de novo. " + DICA_ZIP
        )
    if any(t in msg for t in ("more than 50", "50 files", "than this limit")):
        return (
            "Essa pasta tem arquivos demais para ser baixada pelo link (o Google limita a 50 arquivos por pasta). "
            + DICA_ZIP
        )
    if any(t in msg for t in ("connection", "timeout", "timed out", "network", "resolve", "ssl")):
        return (
            "Não foi possível se conectar ao Google Drive. Verifique sua conexão com a internet e tente novamente."
        )
    return "Não foi possível baixar a pasta do Google Drive neste momento. " + DICA_ZIP


TRABALHADORES_DOWNLOAD = 8  # downloads simultâneos (o gdown baixa um por vez por padrão)

# Arquivos nativos do Google (Docs/Planilhas/Apresentações) não têm download direto: são exportados.
EXPORTACAO_NATIVA = {
    "application/vnd.google-apps.document": ("https://docs.google.com/document/d/{id}/export?format=docx", ".docx"),
    "application/vnd.google-apps.spreadsheet": ("https://docs.google.com/spreadsheets/d/{id}/export?format=xlsx", ".xlsx"),
    "application/vnd.google-apps.presentation": ("https://docs.google.com/presentation/d/{id}/export/pptx", ".pptx"),
}


@dataclass
class ArquivoDrive:
    id: str
    caminho_local: Path
    tipo: str = ""


def _listar_pasta(folder_id: str, pasta_destino: Path) -> list[ArquivoDrive]:
    """Lista todos os arquivos da pasta (recursivamente) sem baixar nada."""
    from gdown.download_folder import _download_and_parse_google_drive_link, _get_directory_structure

    sessao = requests.Session()
    try:
        raiz = _download_and_parse_google_drive_link(
            sess=sessao, folder_id=folder_id, quiet=True, verify=True, timeout=None
        )
    finally:
        sessao.close()

    base = pasta_destino.resolve()
    itens: list[ArquivoDrive] = []
    for arquivo, caminho in _get_directory_structure(gdrive_file=raiz, previous_path=""):
        if arquivo is None:  # subpasta
            continue
        # Os nomes vêm do Drive (controlados por terceiros): impede "../" e caminhos absolutos
        destino = (base / caminho).resolve()
        if not destino.is_relative_to(base):
            continue
        itens.append(ArquivoDrive(id=arquivo.id, caminho_local=destino, tipo=arquivo.type or ""))
    return itens


class _Cota:
    """Bytes que a pasta inteira ainda pode ocupar no disco (compartilhado entre as threads)."""

    def __init__(self, limite: int = MAX_TOTAL_DESCOMPACTADO):
        self._restante = limite
        self._trava = threading.Lock()

    def consumir(self, n: int) -> None:
        with self._trava:
            if n > self._restante:
                raise ErroDrivePersonalizado(
                    f"A pasta passa do limite de {MAX_TOTAL_DESCOMPACTADO // 2**20} MB no total e foi recusada. "
                    + DICA_ZIP
                )
            self._restante -= n

    def devolver(self, n: int) -> None:
        with self._trava:
            self._restante += n


def _gravar_resposta(resp, destino: Path, cota: _Cota) -> None:
    """Grava a resposta em streaming, respeitando o limite por arquivo e a cota da pasta."""
    tmp = destino.with_name(destino.name + ".part")
    recebido = 0
    try:
        with open(tmp, "wb") as f:
            for bloco in resp.iter_content(chunk_size=1 << 16):
                if recebido + len(bloco) > MAX_BYTES_ARQUIVO_DRIVE:
                    raise ErroDrivePersonalizado(
                        f"Um arquivo da pasta passa do limite de {MAX_BYTES_ARQUIVO_DRIVE // 2**20} MB e foi recusado."
                    )
                cota.consumir(len(bloco))
                recebido += len(bloco)
                f.write(bloco)
    except BaseException:
        tmp.unlink(missing_ok=True)
        cota.devolver(recebido)
        raise
    tmp.replace(destino)


def _url_confirmacao(html: str) -> str:
    """Link da página "não foi possível verificar vírus" de arquivos grandes (só domínios do Google)."""
    from gdown.download import get_url_from_gdrive_confirmation

    url = get_url_from_gdrive_confirmation(html)
    host = urlsplit(url).hostname or ""
    if urlsplit(url).scheme != "https" or not (host == "google.com" or host.endswith(".google.com")):
        raise RuntimeError("Cannot retrieve the public link of the file (link de confirmação inesperado)")
    return url


def _baixar_direto(file_id: str, destino: Path, cota: _Cota) -> None:
    """Download direto e rápido (streaming) pelo endpoint público de download do Drive."""
    url = "https://drive.usercontent.google.com/download"
    with requests.get(
        url, params={"id": file_id, "export": "download", "confirm": "t"}, stream=True, timeout=(10, 60)
    ) as resp:
        resp.raise_for_status()
        if "text/html" not in resp.headers.get("content-type", "").lower():
            _gravar_resposta(resp, destino, cota)
            return
        html = resp.text
    # Arquivos grandes podem cair na página de confirmação: segue o link dela, com os mesmos limites
    with requests.get(_url_confirmacao(html), stream=True, timeout=(10, 60)) as resp:
        resp.raise_for_status()
        if "text/html" in resp.headers.get("content-type", "").lower():
            raise RuntimeError("Cannot retrieve the public link of the file (resposta HTML)")
        _gravar_resposta(resp, destino, cota)


def _baixar_arquivo(item: ArquivoDrive, cota: _Cota, tentativas: int = 3) -> None:
    """Baixa (ou exporta, se for nativo do Google) um arquivo, pulando se já estiver em cache."""
    nativo = EXPORTACAO_NATIVA.get(item.tipo)
    if item.tipo.startswith("application/vnd.google-apps.") and nativo is None:
        return  # formulários, atalhos, desenhos etc. não são documentos analisáveis

    destino = item.caminho_local
    if nativo:
        url, extensao = nativo
        if destino.suffix.lower() != extensao:
            destino = destino.with_name(destino.name + extensao)
    if destino.exists() and destino.stat().st_size > 0:
        cota.consumir(destino.stat().st_size)  # o que já está em cache também ocupa o disco
        return
    destino.parent.mkdir(parents=True, exist_ok=True)

    ultimo_erro: Exception | None = None
    for _ in range(tentativas):
        try:
            if nativo:
                with requests.get(url.format(id=item.id), stream=True, timeout=(10, 60)) as resp:
                    if resp.status_code != 200:
                        raise RuntimeError(f"HTTP {resp.status_code} ao exportar o arquivo (permission denied?)")
                    _gravar_resposta(resp, destino, cota)
                return
            _baixar_direto(item.id, destino, cota)
            return
        except ErroDrivePersonalizado:
            raise  # limite de tamanho: tentar de novo não adianta
        except Exception as e:  # noqa: BLE001
            ultimo_erro = e
    raise ultimo_erro or RuntimeError("download falhou")


def baixar_pasta_drive_compartilhada(
    link_ou_id: str, pasta_destino: Path, progresso=None
) -> tuple[Path, str]:
    """Baixa uma pasta compartilhada do Google Drive em paralelo.

    Lista os arquivos uma única vez e baixa vários ao mesmo tempo. Arquivos já baixados
    para o mesmo link são reaproveitados. `progresso(feitos, total)` é chamado a cada arquivo.
    """
    if gdown is None or requests is None:
        raise ErroDrivePersonalizado(
            "A opção de baixar pelo link não está disponível neste computador no momento. " + DICA_ZIP
        )

    folder_id = extrair_id_drive(link_ou_id)
    if not folder_id:
        raise ErroDrivePersonalizado(
            "Esse link não parece ser de uma pasta do Google Drive. Abra a pasta no Drive, clique em "
            "'Compartilhar' > 'Copiar link' e cole aqui (o link começa com https://drive.google.com/drive/folders/...)."
        )

    # Só reaproveita o cache se for a mesma pasta do Drive; senão limpa para não misturar
    marcador = pasta_destino / ".folder_id"
    if pasta_destino.exists() and not (marcador.exists() and marcador.read_text().strip() == folder_id):
        shutil.rmtree(pasta_destino, ignore_errors=True)
    pasta_destino.mkdir(parents=True, exist_ok=True)
    marcador.write_text(folder_id)

    try:
        itens = _listar_pasta(folder_id, pasta_destino)
    except Exception as e:
        raise ErroDrivePersonalizado(_traduzir_erro_drive(e)) from e

    if len(itens) > MAX_ARQUIVOS:
        raise ErroDrivePersonalizado(
            f"A pasta tem arquivos demais ({len(itens)}; limite {MAX_ARQUIVOS}). " + DICA_ZIP
        )
    total = len(itens)
    feitos = 0
    primeiro_erro: Exception | None = None
    cota = _Cota()
    if progresso:
        progresso(0, total)
    with ThreadPoolExecutor(max_workers=TRABALHADORES_DOWNLOAD) as pool:
        futuros = [pool.submit(_baixar_arquivo, item, cota) for item in itens]
        for fut in as_completed(futuros):
            if fut.cancelled():
                continue
            try:
                fut.result()
            except Exception as e:  # noqa: BLE001
                primeiro_erro = primeiro_erro or e
                if isinstance(e, ErroDrivePersonalizado):
                    for f in futuros:  # passou de um limite: não baixa o resto
                        f.cancel()
            feitos += 1
            if progresso:
                progresso(feitos, total)
    if isinstance(primeiro_erro, ErroDrivePersonalizado):
        shutil.rmtree(pasta_destino, ignore_errors=True)
        raise primeiro_erro
    if primeiro_erro is not None:
        raise ErroDrivePersonalizado(_traduzir_erro_drive(primeiro_erro)) from primeiro_erro

    pasta_raiz = detectar_raiz_submissoes(pasta_destino)
    arquivos_baixados = [f for f in pasta_raiz.glob("**/*.*") if f.is_file() and not f.name.startswith(".")]

    if not arquivos_baixados:
        raise ErroDrivePersonalizado(
            "Conseguimos abrir a pasta, mas nenhum documento veio junto. A pasta pode estar vazia "
            "ou os arquivos dentro dela não estão compartilhados. " + DICA_ZIP
        )

    return pasta_raiz, folder_id
