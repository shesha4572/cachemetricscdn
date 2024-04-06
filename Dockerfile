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
ENV ORIGIN_SERVER_URL="http://192.168.0.1:8080"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]