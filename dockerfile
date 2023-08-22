FROM continuumio/miniconda3
WORKDIR /app
COPY . .
# Install all the requirements
RUN conda install -c conda-forge ffmpeg libsndfile
RUN pip install -r requirements.txt
RUN pip install -r requirements-torch.txt
RUN pip install git+https://github.com/m-bain/whisperx.git
RUN apt apt update && apt install ffmpeg

ENTRYPOINT [ "python", "pipeline.py" ]
