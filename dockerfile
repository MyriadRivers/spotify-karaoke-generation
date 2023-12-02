FROM mambaorg/micromamba:0.15.3
ENV NVIDIA_VISIBLE_DEVICES all
ENV NVIDIA_DRIVER_CAPABILITIES all
WORKDIR /app

# Create environment and install reqs
USER root
RUN apt update && apt install -y git

USER micromamba
RUN micromamba install -y -n base python=3.10 -c defaults
RUN micromamba install -y -n base ffmpeg libsndfile -c conda-forge
RUN micromamba install -y -n base pytorch==2.0.0 torchaudio==2.0.0 pytorch-cuda=11.8 -c pytorch -c nvidia -c defaults
USER root
COPY environment.yaml environment.yaml
RUN micromamba install -y -n base -f environment.yaml && micromamba clean --all --yes

RUN apt update && apt install -y ffmpeg

# pytube hotfix
# RUN sed -i 's/transform_plan_raw =.*/transform_plan_raw = js/g' /opt/conda/lib/python3.10/site-packages/pytube/cipher.py

# Copy all the python files
COPY syllabify syllabify
COPY main.py main.py
COPY match_words.py match_words.py
COPY scripts.py scripts.py

CMD [ "python", "-u", "main.py" ]
