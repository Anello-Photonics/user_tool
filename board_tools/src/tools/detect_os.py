# methods to detect OS/instruction set to call programs like bootloader.

# best method in Python seems to be "platform" library: https://docs.python.org/3/library/platform.html
# example results on various os: https://github.com/easybuilders/easybuild/wiki/OS_flavor_name_version
#   system: Linux, Darwin (if Mac), Windows, SunOS
#   machine:
#       x86_64 for lots of Linux
#       i686 on other Linux
#       sun4u for the SunOS example: Sun's own architecture?
#       ppc64 for SUSE Linux Enterprise Server (SLES) 10 - that's a different architecture for PowerPC
#       ia64 for SLES Itanium
#       other SLES have x86_64
#       i386 for some Mac OS X examples, others were x86_64
#       AMD64 for Windows examples.
#       aarch64 on my Raspberry Pi (not on that website)

import platform
import re


# Windows, Linux etc. Note: Mac is "Darwin"
def os_type():
    os_name = platform.system()
    if "darwin" in os_name.lower():
        return "Mac"
    return os_name


def processor_type():
    machine = platform.machine().lower()
    if "x86" in machine:
        return "x86"
    # generic "intel architecture" with 32 or 64 bit. consider this same as x86
    elif ("ia32" in machine) or ("ia64" in machine):
        return "x86"
    # i<digit>86 are Intel architectures, later called "x86". i386, 486, 686 etc, may have more text after.
    elif re.match("i\\d86", machine):
        return "x86"
    # AMD is another designer, should be x86 compatible. Windows computer usually shows "AMD64"
    elif "amd" in machine:
        return "x86"
    # ARM is a different architecture. could be arm6l, arm7l. Don't confuse it with AMD.
    elif "arm" in machine:
        return "arm"
    # linux ARM on Raspberry pi shows "aarch64"
    elif "aarch" in machine:
        return "arm"
    else:
        return machine  # other types: we'll just print "<type> not supported"

# TODO - do we need to detect 32 vs 64 bit? can find that from platform.machine() or platform.architecture().
