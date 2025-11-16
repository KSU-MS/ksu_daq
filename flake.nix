# 🍳 cookin 👩‍🍳
{
  description = "A better python data aquisition flake";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
    flake-utils.url = "github:numtide/flake-utils";
    nix-proto.url = "github:notalltim/nix-proto";
    nix-proto.inputs.nixpkgs.follows = "nixpkgs";
    mcap.url = "github:RCMast3r/py_mcap_nix";
    mcap-protobuf.url = "github:RCMast3r/mcap-protobuf-support-flake";
    asyncudp.url = "github:RCMast3r/asyncudp_nix";
    can_pkg_flake.url = "github:KSU-MS/ksu-ms-dbc/main";
  };

  # Everything your flake needs to produce what it provides
  outputs = { self, nixpkgs, flake-utils, nix-proto, mcap, mcap-protobuf, asyncudp, can_pkg_flake, ... }: 
    flake-utils.lib.eachDefaultSystem (system:
      let
        py_dbc_proto_gen_overlay = final: prev: {
          py_dbc_proto_gen_pkg = final.callPackage ./dbc_proto_gen_script.nix { };
        };
        py_data_acq_overlay = final: prev: {
          py_data_acq_pkg = final.callPackage ./default.nix { };
        };
        proto_gen_overlay = final: prev: {
          proto_gen_pkg = final.callPackage ./dbc_proto_bin_gen.nix { };
        };

        nix_protos_overlays = nix-proto.generateOverlays' {
          hytech_np = { proto_gen_pkg }:
            nix-proto.mkProtoDerivation {
              name = "hytech_np";
              buildInputs = [ proto_gen_pkg ];
              src = proto_gen_pkg.out + "/proto";
              version = "1.0.0";
            };
        };

        my_overlays = [
          py_dbc_proto_gen_overlay
          py_data_acq_overlay
          proto_gen_overlay
          mcap-protobuf.overlays.default
          mcap.overlays.default
          asyncudp.overlays.default
          can_pkg_flake.overlays.default
        ] ++ nix-proto.lib.overlayToList nix_protos_overlays;

        # This combined with the flake-utils package abstracts what architecture you are building for
        pkgs = import nixpkgs { 
          inherit system;
          overlays = my_overlays;
        };


        # Shrimple dev shell to allow for local debug
        devShell = pkgs.mkShell {
          packages = with pkgs; [
            jq
            py_data_acq_pkg
            py_dbc_proto_gen_pkg
            proto_gen_pkg
            can-utils
            can_pkg
          ];

          shellHook = ''
            path=${pkgs.proto_gen_pkg}
            bin_path=$path"/bin"
            dbc_path=${pkgs.can_pkg}
            export BIN_PATH=$bin_path
            export DBC_PATH=$dbc_path

            echo -e "PYTHONPATH=$PYTHONPATH\nBIN_PATH=$bin_path\nDBC_PATH=$dbc_path\n" > .env
          '';
        };

      in {
        overlays.default = nixpkgs.lib.composeManyExtensions my_overlays;

        devShells.default = devShell;
      }
    );
}
