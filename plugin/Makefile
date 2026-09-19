DEVKITARM ?= C:/devkitPro/devkitARM
FAKEMOTE_CIOS_LIB ?= ../../work/fakemote/embedded-game-controller/cios-lib
D2X_CIOS_LIB ?= ../../work/skylanders-research/d2x-cios-full/source/cios-lib

PREFIX := $(DEVKITARM)/bin/arm-none-eabi-
CC := $(PREFIX)gcc
LD := $(PREFIX)gcc
STRIPIOS ?= ../../work/stripios-current-static.exe
CIOS_LIB := $(FAKEMOTE_CIOS_LIB)
BUILD := build

ARCH := -mcpu=arm926ej-s -mthumb -mthumb-interwork -mbig-endian
CFLAGS := $(ARCH) -std=gnu11 -I$(CIOS_LIB) -I$(D2X_CIOS_LIB) -ffreestanding -fno-builtin \
          -ffunction-sections -fomit-frame-pointer -Os -Wall -Wstrict-prototypes
LDFLAGS := $(ARCH) -nostartfiles -nostdlib -Wl,-T,source/link.ld \
           -Wl,--gc-sections -Wl,-static

TARGET := skylanders-hidv5-plugin
OBJS := $(BUILD)/main.o $(BUILD)/start.o $(BUILD)/syscalls.o \
        $(BUILD)/ios.o $(BUILD)/swi_mload.o $(BUILD)/tools.o \
        $(BUILD)/str_utils.o $(BUILD)/isfs.o

all: $(TARGET).elf

$(TARGET).elf: $(OBJS) $(STRIPIOS)
	$(LD) $(LDFLAGS) $(OBJS) -lgcc -o $@.orig
	$(STRIPIOS) $@.orig $@

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/main.o: source/main.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/start.o: source/start.s | $(BUILD)
	$(CC) $(CFLAGS) -D_LANGUAGE_ASSEMBLY -c -x assembler-with-cpp $< -o $@

$(BUILD)/syscalls.o: $(CIOS_LIB)/syscalls.s | $(BUILD)
	$(CC) $(CFLAGS) -D_LANGUAGE_ASSEMBLY -c -x assembler-with-cpp $< -o $@

$(BUILD)/tools.o: $(CIOS_LIB)/tools.s | $(BUILD)
	$(CC) $(CFLAGS) -D_LANGUAGE_ASSEMBLY -c -x assembler-with-cpp $< -o $@

$(BUILD)/ios.o: $(CIOS_LIB)/ios.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/swi_mload.o: $(CIOS_LIB)/swi_mload.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/str_utils.o: $(CIOS_LIB)/str_utils.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/isfs.o: $(D2X_CIOS_LIB)/isfs.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(BUILD)/*.o $(TARGET).elf $(TARGET).elf.orig
