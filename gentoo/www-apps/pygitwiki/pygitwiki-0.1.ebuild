EAPI="6"

PYTHON_COMPAT=( python3_{4,5,6} )

inherit python-r1 systemd eutils

DESCRIPTION="A lightweight Wiki using a Git storage backend for personal use"
HOMEPAGE="https://github.com/Rainer-Keller/PyGitWiki"
SRC_URI="https://github.com/Rainer-Keller/PyGitWiki/archive/v${PV}.tar.gz -> ${P}.tar.gz"
LICENSE="GPL-3"
SLOT="0"
KEYWORDS="~amd64 ~x86"

RDEPEND="${PYTHON_DEPS}
    dev-python/markdown[${PYTHON_USEDEP}]
    dev-python/git-python[${PYTHON_USEDEP}]
    dev-vcs/git"

REQUIRED_USE="${PYTHON_REQUIRED_USE}"

S="${WORKDIR}/PyGitWiki-${PV}"

src_prepare() {
    eapply_user "${FILESDIR}/0001-Fix-dataDir.patch"
}

src_install() {
    python_foreach_impl python_newscript wiki.py pygitwiki
    dodir /usr/share/pygitwiki
    insinto /usr/share/pygitwiki
    doins "${S}/stylesheet.css"
    doins "${S}/edit.html"
    doins "${S}/notfound.html"
    doins "${S}/search.html"
    doins "${S}/view.html"
    doins "${S}/wiki.systemconf"
    doins "${S}/wiki.conf.example"
    systemd_douserunit "${S}"/gentoo/pygitwiki.service
}
