# ==========================================
# Fase 1: Build (Ambiente di compilazione)
# ==========================================
# Specifica la piattaforma del builder per velocizzare il processo
FROM --platform=$BUILDPLATFORM golang:alpine AS builder

WORKDIR /app

# Copia i file delle dipendenze e scaricale
COPY go.mod go.sum ./
RUN go mod download

# Copia tutto il codice sorgente
COPY . .

# Queste due righe "catturano" l'architettura che buildx sta processando in quel momento
ARG TARGETOS
ARG TARGETARCH

# Compila l'agente usando le variabili dinamiche invece di forzare amd64!
RUN CGO_ENABLED=0 GOOS=$TARGETOS GOARCH=$TARGETARCH go build -ldflags="-s -w" -o edgehub-agent cmd/agent/main.go

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