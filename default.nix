{ lib
, python313Packages
, fetchurl
, mcap_support_pkg
, py_mcap_pkg
, asyncudp_pkg
, hytech_np_proto_py
, proto_gen_pkg
}:

let
  foxglove-sdk = python313Packages.buildPythonPackage {
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
python313Packages.buildPythonApplication {
  pname = "py_data_acq";
  version = "1.0.1";

  propagatedBuildInputs = [
    python313Packages.cantools
    python313Packages.systemd
    python313Packages.websockets
    python313Packages.pprintpp
    python313Packages.can
    python313Packages.pyserial-asyncio
    python313Packages.lz4
    python313Packages.zstandard
    python313Packages.protobuf
    asyncudp_pkg
    foxglove-sdk
    mcap_support_pkg
    py_mcap_pkg
    hytech_np_proto_py
    proto_gen_pkg
  ];

  src = ./py_data_acq;
}
