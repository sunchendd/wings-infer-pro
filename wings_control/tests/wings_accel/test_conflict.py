from wings_accel.conflict import resolve_conflicts
from wings_accel.render import PlaceholderContext
from wings_accel.schemas import EngineParams, _FeatureOutput


def make_output(scheme, degraded=False, reason="", cli=None):
    return _FeatureOutput(
        scheme=scheme,
        engine_params=EngineParams(engine_config=cli or []),
        degraded=degraded,
        degrade_reason=reason,
    )


CTX = PlaceholderContext()


def test_resolve_conflicts_is_noop_when_decoding_none():
    dec, spa, off, extra = resolve_conflicts(None, None, make_output("cpu"), None, CTX)
    assert dec is None
    assert off.scheme == "cpu"
    assert not extra


def test_mtp_lmcache_no_longer_conflicts():
    dec = make_output("mtp")
    off = make_output("disk", cli=["--kv-transfer-config", '{"kv_connector":"LMCacheConnectorV1"}'])
    dec_out, _, off_out, extra = resolve_conflicts(dec, None, off, [], CTX)
    assert dec_out is dec
    assert dec_out.scheme == "mtp"
    assert off_out is off
    assert not extra


def test_degraded_mtp_lmcache_no_longer_conflicts():
    dec = make_output("mtp", degraded=True, reason="model_based_miss->no_model")
    off = make_output("disk", cli=["--kv-transfer-config", '{"kv_connector":"LMCacheConnectorV1"}'])
    dec_out, _, off_out, extra = resolve_conflicts(dec, None, off, [], CTX)
    assert dec_out is dec
    assert dec_out.degraded is True
    assert off_out is off
    assert not extra
