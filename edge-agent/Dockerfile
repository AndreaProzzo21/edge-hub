# ==========================================
# Fase 1: Build (Ambiente di compilazione)
# ==========================================
FROM golang:alpine AS builder

WORKDIR /app

# Copia i file delle dipendenze e scaricale
COPY go.mod go.sum ./
RUN go mod download

# Copia tutto il codice sorgente
COPY . .

# Compila l'agente come binario statico
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -ldflags="-s -w" -o edgehub-agent cmd/agent/main.go

# ==========================================
# Fase 2: Immagine di Produzione leggerissima
# ==========================================
FROM alpine:latest

# Aggiunge i certificati SSL (fondamentali per le chiamate HTTPS verso il tuo backend)
RUN apk --no-cache add ca-certificates tzdata

WORKDIR /app

# Copia SOLO l'eseguibile compilato dalla fase 1
COPY --from=builder /app/edgehub-agent .

# Rende il file eseguibile (per sicurezza)
RUN chmod +x /app/edgehub-agent

# Comando di default all'avvio del container
CMD ["/app/edgehub-agent"]