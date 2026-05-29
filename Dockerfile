## Minimal image shown when setup hasn't been run yet
FROM alpine:latest AS not-configured
WORKDIR /app
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]

## Stage 1: Build GpssConsole (updated or default)
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS dotnet-build
ARG UPDATE_LEGALITY=false
ARG PKHEX_TAG=unused
WORKDIR /src

RUN if [ "$UPDATE_LEGALITY" = "true" ]; then \
        echo "Building legality engine (PKHeX $PKHEX_TAG)..." && \
        git clone --depth 1 --branch "$PKHEX_TAG" https://github.com/kwsch/PKHeX.git && \
        git clone --depth 1 --branch "$PKHEX_TAG" https://github.com/santacrab2/PKHeX-Plugins.git && \
        git clone --depth 1 https://github.com/FlagBrew/local-gpss.git && \
        dotnet build PKHeX/PKHeX.Core/PKHeX.Core.csproj -c Release && \
        dotnet build PKHeX-Plugins/PKHeX.Core.AutoMod/PKHeX.Core.AutoMod.csproj -c Release && \
        cp PKHeX/PKHeX.Core/bin/Release/net10.0/PKHeX.Core.dll \
           local-gpss/GpssConsole/deps/PKHeX.Core.dll && \
        cp PKHeX-Plugins/PKHeX.Core.AutoMod/bin/Release/net10.0/PKHeX.Core.AutoMod.dll \
           local-gpss/GpssConsole/deps/PKHeX.Core.AutoMod.dll && \
        sed -i 's/pokemon\.Context\.Generation()/pokemon.Context.Generation/g' \
            local-gpss/GpssConsole/utils/PKhex.cs && \
        sed -i '/PokemonBase64 = Convert/,/: pokemon\.DecryptedBoxData);/c\        var buf = new byte[pokemon.SIZE_PARTY > pokemon.SIZE_STORED ? pokemon.SIZE_PARTY : pokemon.SIZE_STORED];\n        if (pokemon.SIZE_PARTY > pokemon.SIZE_STORED)\n            pokemon.WriteDecryptedDataParty(buf);\n        else\n            pokemon.WriteDecryptedDataStored(buf);\n        PokemonBase64 = Convert.ToBase64String(buf);' \
            local-gpss/GpssConsole/models/Legality.cs && \
        dotnet publish local-gpss/GpssConsole/GpssConsole.csproj -c Release \
            -r linux-x64 --self-contained \
            -p:PublishSingleFile=true -p:IncludeNativeLibrariesForSelfExtract=true \
            -o /out; \
    else \
        echo "Using bundled legality engine..." && \
        apt-get update -qq && apt-get install -y -qq unzip curl > /dev/null && \
        GPSS_TAG=$(curl -sL https://api.github.com/repos/FlagBrew/local-gpss/releases/latest | grep '"tag_name"' | head -1 | cut -d'"' -f4) && \
        curl -sL -o linux64.zip "https://github.com/FlagBrew/local-gpss/releases/download/${GPSS_TAG}/linux64.zip" && \
        unzip -q linux64.zip && \
        mkdir -p /out && \
        cp bin/GpssConsole /out/GpssConsole; \
    fi

## Stage 2: Build latest local-gpss server
FROM golang:alpine AS go-build
WORKDIR /src

RUN apk add --no-cache git
RUN git clone --depth 1 https://github.com/FlagBrew/local-gpss.git .

# Patch progress output: add \n so lines flush instead of being stuck in Go's buffer
RUN sed -i 's/fmt\.Printf("Checked: %d\/%d, failed: %d"/fmt.Printf("Checked: %d\/%d, failed: %d\\n"/' \
        internal/utils/migrate.go && \
    sed -i 's/fmt\.Printf("Created: %d\/%d\\r"/fmt.Printf("Created: %d\/%d\\n"/' \
        internal/utils/migrate.go

RUN CGO_ENABLED=0 go build \
    -ldflags '-d -s -w -extldflags=-static' \
    -tags=netgo,osusergo,static_build \
    -installsuffix netgo \
    -buildvcs=false \
    -trimpath \
    -o /out/local-gpss

## Stage 3: Full runtime
FROM alpine:latest AS runtime

WORKDIR /app

RUN apk add --no-cache gcompat libstdc++ libgcc icu-libs python3 && \
    mkdir bin

COPY --from=dotnet-build /out/GpssConsole ./bin/GpssConsole
COPY --from=go-build /out/local-gpss ./local-gpss
COPY entrypoint.sh ./entrypoint.sh
COPY viewer ./viewer

RUN echo "MODE=docker" > .env && \
    chmod +x entrypoint.sh bin/GpssConsole viewer/patch_gpss_port.py viewer/server.py

EXPOSE 8082

ENTRYPOINT ["/app/entrypoint.sh"]
