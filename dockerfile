FROM continuumio/miniconda3
WORKDIR /app
COPY . .
# Install all the requirements
RUN conda create -n karaoke-generation python=3.10
SHELL ["conda", "run", "-n", "karaoke-generation", "/bin/bash", "-c"]
RUN conda install -c conda-forge ffmpeg libsndfile
RUN pip install spleeter
RUN pip install -r requirements.txt
RUN pip install -r requirements-torch.txt
RUN pip install git+https://github.com/m-bain/whisperx.git
RUN apt update && apt install -y ffmpeg

ENTRYPOINT ["conda", "run", "-n", "karaoke-generation", "python", "pipeline.py"]
