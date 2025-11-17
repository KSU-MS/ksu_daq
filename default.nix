{ lib
, python311Packages
, fetchurl
, mcap_support_pkg
, py_mcap_pkg
, asyncudp_pkg
, hytech_np_proto_py
, proto_gen_pkg
}:

let
  foxglove-sdk = python311Packages.buildPythonPackage rec {
    pname = "foxglove-sdk";
    version = "0.15.3";
    format = "wheel";

    src = fetchurl {
      url = "https://files.pythonhosted.org/packages/3b/f5/76095ec60d458cbe1fc1120f6230b85d451eebc829ca13b209fa41020bc8/foxglove_sdk-0.15.3-cp311-cp311-manylinux_2_17_aarch64.manylinux2014_aarch64.whl";
      sha256 = "q6hdNPKSyn3N8rHW3Jvy1aZTHjfBAjsRAXNKX+HXrPw=";
    };

    doCheck = false;
    pythonImportsCheck = [ "foxglove" ];

  };
in
python311Packages.buildPythonApplication {
  pname = "py_data_acq";
  version = "1.0.1";

  propagatedBuildInputs = [
    python311Packages.cantools
    python311Packages.systemd
    python311Packages.websockets
    python311Packages.pprintpp
    python311Packages.can
    python311Packages.pyserial-asyncio
    asyncudp_pkg
    python311Packages.lz4
    python311Packages.zstandard
    foxglove-sdk
    python311Packages.protobuf
    mcap_support_pkg
    py_mcap_pkg
    hytech_np_proto_py
    proto_gen_pkg
  ];

  src = ./py_data_acq;
}
