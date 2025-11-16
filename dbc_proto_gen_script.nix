{ lib, python313Packages }:

python313Packages.buildPythonApplication {
  pname = "py_dbc_proto_gen";
  version = "1.0.0";

  
  propagatedBuildInputs = [ 
    python313Packages.cantools 
    python313Packages.protobuf 
    python313Packages.requests 
  ];

  src = ./py_dbc_proto_gen;
}
