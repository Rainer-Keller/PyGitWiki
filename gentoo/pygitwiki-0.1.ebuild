EAPI="6"

PYTHON_COMPAT=( python3_{4,5,6} )

inherit python-single-r1 systemd

DESCRIPTION="A lightweight Wiki using a Git storage backend for personal use"
HOMEPAGE="https://github.com/Rainer-Keller/PyGitWiki"
SRC_URI="https://github.com/Rainer-Keller/PyGitWiki/archive/${P}.tar.gz"
LICENSE="GPL-3"
SLOT="0"
KEYWORDS="~amd64 ~x86"

RDEPEND="${PYTHON_DEPS}
    dev-python/markdown[${PYTHON_USEDEP}]
    dev-python/git-python[${PYTHON_USEDEP}]
"
DEPEND="dev-vcs/git"

REQUIRED_USE="${PYTHON_REQUIRED_USE}"

S="${WORKDIR}"/${P}

src_install() {
    python_newscript wiki.py pygitwiki
    dodir /usr/share/pygitwiki
    cp -R "${S}/" "${D}/usr/share/pygitwiki/" || die "Install failed!"
    systemd_douserunit "${S}"/gentoo/pygitwiki.service
}