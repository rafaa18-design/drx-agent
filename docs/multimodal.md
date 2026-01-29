# Multimodal (Imagens, Áudio, Vídeo)

O Agno suporta entrada e saída multimodal para processamento de imagens, áudio e vídeo.

---

## Conceitos

| Conceito | Descrição |
|----------|-----------|
| **Image** | Imagens via URL, bytes ou filepath |
| **Audio** | Áudio para transcrição ou análise |
| **Video** | Vídeo para análise (Gemini) |
| **modalities** | Configuração de output (text, audio) |

---

## Imagens

### Via URL

```python
from agno.agent import Agent
from agno.media import Image
from agno.models.openai import OpenAIChat
from agno.tools.duckduckgo import DuckDuckGoTools

agent = Agent(
    model=OpenAIChat(id="gpt-4o-mini"),
    tools=[DuckDuckGoTools()],
    markdown=True,
)

agent.print_response(
    "Tell me about this image and give me the latest news about it.",
    images=[
        Image(url="https://upload.wikimedia.org/wikipedia/commons/0/0c/GoldenGateBridge-001.jpg")
    ],
    stream=True,
)
```

### Via Bytes

```python
from pathlib import Path
from agno.agent import Agent
from agno.media import Image
from agno.models.openai import OpenAIChat

agent = Agent(
    model=OpenAIChat(id="gpt-4o-mini"),
    markdown=True,
)

# Ler imagem como bytes
image_path = Path("./sample.jpg")
image_bytes = image_path.read_bytes()

agent.print_response(
    "What's in this image?",
    images=[Image(content=image_bytes)],
    stream=True,
)
```

### Via URL como Bytes

```python
import requests
from agno.agent import Agent
from agno.media import Image
from agno.models.mistral import MistralChat

agent = Agent(
    model=MistralChat(id="pixtral-12b-2409"),
    markdown=True,
)

image_url = "https://example.com/image.jpeg"

def fetch_image_bytes(url: str) -> bytes:
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.content

image_bytes = fetch_image_bytes(image_url)

agent.print_response(
    "Describe this image.",
    images=[Image(content=image_bytes)],
)
```

### Múltiplas Imagens

```python
agent.print_response(
    "Compare these two images.",
    images=[
        Image(url="https://example.com/image1.jpg"),
        Image(url="https://example.com/image2.jpg"),
    ],
)
```

### Com Gemini

```python
from agno.agent import Agent
from agno.media import Image
from agno.models.google import Gemini

agent = Agent(
    model=Gemini(id="gemini-2.0-flash"),
    markdown=True,
)

agent.print_response(
    "Tell me about this image.",
    images=[Image(url="https://upload.wikimedia.org/...")],
)
```

---

## Áudio

### Transcrição com Whisper

```python
from pathlib import Path
from agno.agent import Agent
from agno.tools.openai import OpenAITools
from agno.utils.media import download_file

# Download do áudio
url = "https://agno-public.s3.amazonaws.com/demo_data/sample_conversation.wav"
local_path = Path("tmp/sample.wav")
download_file(url, local_path)

# Agente de transcrição
agent = Agent(
    tools=[OpenAITools(transcription_model="gpt-4o-transcribe")],
    markdown=True,
)

agent.print_response(f"Transcribe the audio file: {local_path}")
```

### Transcrição com Groq

```python
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.models.groq import GroqTools

url = "https://agno-public.s3.amazonaws.com/demo_data/sample_conversation.wav"

agent = Agent(
    name="Transcription Agent",
    model=OpenAIChat(id="gpt-4o-mini"),
    tools=[GroqTools(exclude_tools=["generate_speech"])],
)

agent.print_response(f"Transcribe the audio file at '{url}' to English")
```

### Análise de Áudio com Gemini

```python
import requests
from agno.agent import Agent
from agno.media import Audio
from agno.models.google import Gemini

agent = Agent(
    model=Gemini(id="gemini-2.0-flash-exp"),
    markdown=True,
)

url = "https://agno-public.s3.amazonaws.com/demo_data/QA-01.mp3"
response = requests.get(url)
audio_content = response.content

agent.print_response(
    "Give a transcript of this audio. Use Speaker A, Speaker B to identify speakers.",
    audio=[Audio(content=audio_content)],
    stream=True,
)
```

### Áudio como Input e Output (OpenAI)

```python
from textwrap import dedent
import requests
from agno.agent import Agent
from agno.media import Audio
from agno.models.openai import OpenAIChat
from agno.utils.audio import write_audio_to_file

# Agente com output de áudio
agent = Agent(
    model=OpenAIChat(
        id="gpt-4o-mini-audio-preview",
        modalities=["text", "audio"],  # Output em texto e áudio
        audio={"voice": "sage", "format": "wav"},
    ),
    description="You are an audio processing expert.",
    instructions=dedent("""
        Listen to audio input carefully.
        Provide clear, concise responses.
        Maintain a natural, conversational tone.
    """),
)

# Buscar áudio de exemplo
url = "https://openaiassets.blob.core.windows.net/$web/API/docs/audio/alloy.wav"
response = requests.get(url)

# Processar e obter resposta
run_response = agent.run(
    "What's in this recording? Analyze the content and tone.",
    audio=[Audio(content=response.content, format="wav")],
)

# Salvar resposta de áudio
if run_response.response_audio is not None:
    write_audio_to_file(
        audio=run_response.response_audio.content,
        filename="tmp/response.wav",
    )
```

---

## Vídeo

O suporte a vídeo está disponível principalmente com modelos Gemini.

### Via Filepath

```python
from pathlib import Path
from agno.agent import Agent
from agno.media import Video
from agno.models.google import Gemini

agent = Agent(
    model=Gemini(id="gemini-2.0-flash-001"),
    markdown=True,
)

# Download: wget https://storage.googleapis.com/generativeai-downloads/images/GreatRedSpot.mp4
video_path = Path("./GreatRedSpot.mp4")

agent.print_response(
    "Tell me about this video",
    videos=[Video(filepath=video_path)],
)
```

### Via URL (Bytes)

```python
import requests
from agno.agent import Agent
from agno.media import Video
from agno.models.google import Gemini

agent = Agent(
    model=Gemini(id="gemini-2.0-flash-exp"),
    markdown=True,
)

url = "https://videos.pexels.com/video-files/5752729/5752729-uhd_2560_1440_30fps.mp4"

# Download do vídeo
response = requests.get(url)
video_content = response.content

agent.print_response(
    "Tell me about this video",
    videos=[Video(content=video_content)],
)
```

---

## Multimodal em Teams

```python
from agno.agent import Agent
from agno.team import Team

team = Team(
    members=[
        Agent(
            name="Visual Analyst",
            role="Analyze visual content",
            instructions="Focus on visual details",
        ),
        Agent(
            name="Content Writer",
            role="Create descriptions",
            instructions="Write clear summaries",
        ),
    ],
)

team.print_response(
    [
        {"type": "text", "text": "What's in this image?"},
        {
            "type": "image_url",
            "image_url": {
                "url": "https://example.com/image.jpg",
            },
        },
    ],
    stream=True,
    markdown=True,
)
```

---

## Configurações de Media

```python
from agno.agent import Agent
from agno.models.openai import OpenAIChat

agent = Agent(
    model=OpenAIChat(id="gpt-4o-mini"),
    # Enviar media para o modelo (default: True)
    send_media_to_model=True,
    # Armazenar media no banco (default: True)
    store_media=True,
)
```

---

## Suporte por Modelo

| Modelo | Imagem | Áudio | Vídeo |
|--------|--------|-------|-------|
| GPT-4o/4o-mini | ✅ | ✅ | ❌ |
| GPT-4o-audio-preview | ✅ | ✅ (I/O) | ❌ |
| Claude 3.5 | ✅ | ❌ | ❌ |
| Gemini 2.0 | ✅ | ✅ | ✅ |
| Pixtral | ✅ | ❌ | ❌ |
| Llama Vision | ✅ | ❌ | ❌ |

---

## Referências

- [Agno Images](https://docs.agno.com/basics/multimodal/images/image-input)
- [Agno Audio](https://docs.agno.com/basics/multimodal/audio/speech-to-text)
- [Agno Video](https://docs.agno.com/basics/multimodal/video/video_input)
