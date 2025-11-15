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
      url = "https://files.pythonhosted.org/packages/89/2c/6dc049ff39f5cc7b499cebc64821af35d592875caf57976568ddb5bd93fa/foxglove_sdk-0.15.3-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl";
      sha256 = "1n7ic5dpvyg9kgy6pgzy9n0pijjw8rn1i4r5bk94jrc0ppm9fys8";
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
