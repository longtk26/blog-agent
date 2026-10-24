FROM minlag/mermaid-cli:latest

USER root
WORKDIR /app

COPY server.js /app/server.js

ENV PORT=8080
EXPOSE 8080

ENTRYPOINT ["node", "/app/server.js"]
