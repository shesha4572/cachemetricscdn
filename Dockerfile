FROM python:3.11
WORKDIR /code
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
COPY . /code/app
RUN mkdir /mpd
RUN mkdir /seg
ENV MPD_DIR="/mpd"
EXPOSE 8000
ENV SEG_CACHE_DIR="/seg"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]