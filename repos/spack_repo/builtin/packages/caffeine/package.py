# Copyright Spack Project Developers. See COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os
import stat

from spack_repo.builtin.build_systems.generic import Package

from spack.package import *


class Caffeine(Package):
    """
    Caffeine is a parallel runtime library that supports Fortran compilers by
    providing a portable implementation of the Fortran multi-image features on
    shared- and distributed-memory POSIX platforms. Caffeine is the first
    implementation of the Parallel Runtime Interface for Fortran (PRIF), a
    compiler-independent runtime library interface that isolates the Fortran
    compiler from details of the communication stack.
    """

    homepage = "https://go.lbl.gov/caffeine"
    url = "https://github.com/BerkeleyLab/caffeine/archive/refs/tags/0.8.4.tar.gz"
    #git = "https://github.com/BerkeleyLab/caffeine.git"
    git = "https://github.com/bonachea/caffeine.git"

    maintainers("bonachea")

    license("BSD-3-Clause-LBNL")

    version("main", branch="main")
    version("stable", branch="spack")

    version("0.8.4", sha256="34befb91dc04ec3fb5cbcb98f56711419e0c907e3b6e693549e358a34783b9f9")
    version("0.8.2", sha256="9dc8ebd8f9fda1a19426d9a419c7e3533808a011a7f44991a66972e89a19079e")
    # versions prior to 0.8.2 are unsupported due to significant installer changes

    provides("prif")
    provides("prif@0.8", when="@0.8:")

    patch("install_via_spack.patch", when="@0.8")

    variant("debug", default=False, description="Enable library correctness-checking mode")
    variant("fpm", default=False, description="Build using the Fortran Package Manager")
    variant("verbose", default=False, description="Build with verbosity")

    network_values = ("smp", "ibv", "udp", "ofi", "ucx")
    variant(
        "network",
        default="smp",
        values=network_values,
        multi=False,
        sticky=True,
        description="The hardware-dependent network backend to enable.\n"
        + "(smp) = SMP conduit for single-node operation\n"
        + "(ibv) = Native InfiniBand verbs conduit\n"
        + "(ofi) = OFI conduit over libfabric, for HPE Cray Slingshot and Intel Omni-Path\n"
        + "(udp) = Portable UDP conduit, for Ethernet networks\n"
        + "(ucx) = EXPERIMENTAL UCX conduit for Mellanox IB/RoCE ConnectX-5+\n"
        + "For detailed recommendations, consult https://gasnet.lbl.gov",
    )

    depends_on("curl", type="build")
    depends_on("git@1.8:", type="build")
    depends_on("gmake@3.8:", type="build")
    depends_on("pkgconfig", type="build")
    depends_on("perl", type=("build","run"))

    depends_on("fpm@0.10:", type="build", when="+fpm")
    depends_on("cmake@3:", type="build", when="~fpm")

    depends_on("c", type="build")
    depends_on("fortran", type="build")

    # Require a supported Fortran/C compiler combination
    requires(
        "%fortran,c=clang@19:",
        "%fortran,c=gcc@13:",
        "%fortran=lfortran@0.63:",
        policy="any_of",
        msg="Caffeine currently supports LLVM Flang, GNU Gfortran and LFortran"
    )

    # Propagate settings to GASNet:
    depends_on("gasnet +debug", when="+debug", type="all")
    depends_on("gasnet ~debug", when="~debug", type="all")
    for net in network_values:
        depends_on(f"gasnet threadmode=seq conduits={net}", when=f"network={net}", type="all")

    # Caffeine requires GASNet built with the same C compiler:
    for ver in range(19, 24):
        depends_on(f"gasnet %clang@{ver}", when=f"%clang@{ver}")
    for ver in range(13, 17):
        depends_on(f"gasnet %gcc@{ver}", when=f"%gcc@{ver}")

    def setup_build_environment(self, env: EnvironmentModifications) -> None:
        env.set("FC", self.compiler.fc)
        env.set("CC", self.compiler.cc)
        # Ensure Caffeine detects the Spack-provided tools (esp make)
        env.set("MAKE", self.spec["gmake"].prefix.bin.make)
        if (self.spec.satisfies("+fpm")):
            env.set("FPM", self.spec["fpm"].prefix.bin.fpm)
        else:
            env.set("CMAKE", self.spec["cmake"].prefix.bin.cmake)
        env.set("PKG_CONFIG", self.spec["pkgconfig"].prefix.bin + "/pkg-config")

    def install(self, spec, prefix):
        script = Executable("./install.sh")
        script(*self.install_args())

    def enable_or_disable(self, option_name, value):
        if value:
            return [f"--enable-{option_name}"]
        return [f"--disable-{option_name}"]

    def install_args(self):
        spec = self.spec
        args = []
        if spec.satisfies("+verbose"):
            args.append("--verbose")
        args.append("--prefix={0}".format(self.prefix))
        args.append("--enable-spack-install")
        args.append("--network={0}".format(spec.variants["network"].value))
        args += self.enable_or_disable("debug", spec.satisfies("+debug"))
        args += self.enable_or_disable("fpm", spec.satisfies("+fpm"))
        return args

    @run_after("install")
    @on_package_attributes(run_tests=True)
    def check_install(self):
        if self.spec.satisfies("network=smp"):
            if self.spec.satisfies("+fpm"):
                # build and run Julienne-based unit tests
                script = Executable("./run-fpm.sh")
                script("test")

            # Run native multi-image test
            make("-C", "app", "prif")

