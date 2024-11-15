import pytest

from dnstapir.dns.mozpsl import PublicSuffixList

MOZ_PSL = "https://publicsuffix.org/list/public_suffix_list.dat"


def test_mozpsl():
    psl = PublicSuffixList()
    psl.load_psl_url(url=MOZ_PSL)

    assert psl.coredomain("www.ck.") == ("www.ck", "")
    assert psl.coredomain("www.something.gov.ck.") == ("something.gov.ck", "")
    assert psl.coredomain("www.something.or.other.microsoft.com.") == ("microsoft.com", "")
    assert psl.coredomain("www.something.or.other.microsoft.com.br.") == ("microsoft.com.br", "")
    assert psl.coredomain("www.something.emrstudio-prod.us-gov-east-1.amazonaws.com.") == (
        "amazonaws.com",
        "something.emrstudio-prod.us-gov-east-1.amazonaws.com",
    )
    assert psl.rdomain("com.amazonaws.us-gov-east-1.emrstudio-prod.www.something.emrstudio-prod") == (
        "com.amazonaws",
        "com.amazonaws.us-gov-east-1.emrstudio-prod.www",
    )

    with pytest.raises(KeyError):
        psl.coredomain("local.")

    # IDN test
    assert psl.coredomain("www.xn--mnchen-3ya.de.") == ("xn--mnchen-3ya.de", "")

    # Edge cases
    with pytest.raises(ValueError):
        psl.coredomain("")
    with pytest.raises(ValueError):
        psl.coredomain(None)
    with pytest.raises(KeyError):
        psl.coredomain("invalid..domain.")
