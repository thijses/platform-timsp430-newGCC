# Copyright 2014-present PlatformIO <contact@platformio.org>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
from os.path import join

from SCons.Script import (COMMAND_LINE_TARGETS, AlwaysBuild, Builder, Default,
                          DefaultEnvironment)

env = DefaultEnvironment()

env.Replace(
    AR="msp430-elf-ar",
    AS="msp430-elf-as",
    CC="msp430-elf-gcc",
    CXX="msp430-elf-g++",
    GDB="msp430-elf-gdb",
    OBJCOPY="msp430-elf-objcopy",
    RANLIB="msp430-elf-ranlib",
    SIZETOOL="msp430-elf-size",
    LINK="$CC",

    ARFLAGS=["rc"],

    PIODEBUGFLAGS=["-O0", "-g3", "-ggdb", "-gdwarf-2"],

    SIZEPROGREGEXP=r"^(?:\.text|\.data|\.rodata|\.vectors)\s+([0-9]+).*",
    SIZEDATAREGEXP=r"^(?:\.data|\.bss|\.noinit)\s+(\d+).*",
    SIZECHECKCMD="$SIZETOOL -A -d $SOURCES",
    SIZEPRINTCMD='$SIZETOOL -B -d $SOURCES',

    UPLOADER="mspdebug",
    UPLOADERFLAGS=[
        "$UPLOAD_PROTOCOL",
        "--force-reset"
    ],
    UPLOADCMD='$UPLOADER $UPLOADERFLAGS "prog $SOURCES"',

    PROGSUFFIX=".elf"
)

machine_flags = [
    "-mmcu=$BOARD_MCU",
]

env.Append(
    ASFLAGS=machine_flags,
    ASPPFLAGS=[
        "-x", "assembler-with-cpp",
    ],

    CCFLAGS=machine_flags + [
        "-Os",
        "-ffunction-sections",  # place each function in its own section
        "-fdata-sections",
        "-mlarge", # use large memory-model automatically.
        "-mcode-region=either", # https://github.com/maxgerhardt/platform-timsp430
        "-mdata-region=either"  # github user maxgerhardt added this fix
    ],

    CXXFLAGS=[
        "-fno-exceptions",
        "-fno-threadsafe-statics"
    ],

    CPPDEFINES=[
        ("F_CPU", "$BOARD_F_CPU")
    ],

    LINKFLAGS=machine_flags + [
        "-Os",
        "-Wl,-gc-sections,-u,main",
        "-mlarge", # use large memory-model also at the linker stage
        "-mcode-region=either", # https://github.com/maxgerhardt/platform-timsp430
        "-mdata-region=either"  # github user maxgerhardt added this fix
    ],

    LIBS=["m"],

    BUILDERS=dict(
        ElfToHex=Builder(
            action=env.VerboseAction(" ".join([
                "$OBJCOPY",
                "-O",
                "ihex",
                "-R",
                ".eeprom",
                "$SOURCES",
                "$TARGET"
            ]), "Building $TARGET"),
            suffix=".hex"
        )
    )
)

# Allow user to override via pre:script
if env.get("PROGNAME", "program") == "program":
    env.Replace(PROGNAME="firmware")

if "energia" in env.get("PIOFRAMEWORK", []):
    sys.stderr.write(
        "WARNING!!! Using of `framework = energia` in `platformio.ini` is "
        "deprecated. Please replace with `framework = arduino`.\n")
    env.Replace(PIOFRAMEWORK=["arduino"])

#
# Target: Build executable and linkable firmware
#

target_elf = None
if "nobuild" in COMMAND_LINE_TARGETS:
    target_elf = join("$BUILD_DIR", "${PROGNAME}.elf")
    target_firm = join("$BUILD_DIR", "${PROGNAME}.hex")
else:
    target_elf = env.BuildProgram()
    target_firm = env.ElfToHex(join("$BUILD_DIR", "${PROGNAME}"), target_elf)
    env.Depends(target_firm, "checkprogsize")

AlwaysBuild(env.Alias("nobuild", target_firm))
target_buildprog = env.Alias("buildprog", target_firm, target_firm)

#
# Target: Print binary size
#

target_size = env.Alias(
    "size", target_elf,
    env.VerboseAction("$SIZEPRINTCMD", "Calculating size $SOURCE"))
AlwaysBuild(target_size)

#
# Target: Upload firmware
#

upload_target = target_firm
if env.subst("$UPLOAD_PROTOCOL") == "dslite":
    env.Replace(
        UPLOADER=join(env.PioPlatform().get_package_dir(
            "tool-dslite") or "", "DebugServer", "bin", "DSLite"),
        UPLOADERFLAGS=[
            "load", "-c",
            join(env.PioPlatform().get_package_dir("tool-dslite") or "",
                 "%s.ccxml" % env.BoardConfig().get("build.variant")), "-f"
        ],
        UPLOADCMD="$UPLOADER $UPLOADERFLAGS $SOURCES"
    )
    upload_target = target_elf
    upload_actions = [env.VerboseAction("$UPLOADCMD", "Uploading $SOURCE")]

target_upload = env.Alias("upload", upload_target,
                          env.VerboseAction("$UPLOADCMD", "Uploading $SOURCE"))
AlwaysBuild(target_upload)

#
# Default targets
#

Default([target_buildprog, target_size])
