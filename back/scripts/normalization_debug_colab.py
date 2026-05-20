from __future__ import annotations

import argparse
import asyncio
import json

from app.services.normalization_debug_helper import debug_normalize_from_paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Debug normalization for Colab-like flow")
    parser.add_argument("--image", required=True, help="Path de imagen a normalizar")
    parser.add_argument("--profile-source", default=None, help="Fuente de perfiles: json|redis|mongo")
    parser.add_argument("--compare-image", default=None, help="Path imagen de comparacion")
    parser.add_argument("--compare-profile-json", default=None, help="Path JSON de perfil comparacion")

    parser.add_argument("--name", default=None, help="Nombre paciente")
    parser.add_argument("--lastname", default=None, help="Apellido paciente")
    parser.add_argument("--sex", default=None, help="Sexo paciente")
    parser.add_argument("--age", type=int, default=None, help="Edad paciente")
    parser.add_argument("--weight", type=float, default=None, help="Peso paciente")
    parser.add_argument("--timestamp", default=None, help="Timestamp manual")
    parser.add_argument("--debug-save-json", action="store_true", help="Forzar guardado JSON de traza")
    parser.add_argument("--trace-generate-visualization", action="store_true", help="Generar imagen de visualizacion")
    parser.add_argument("--no-trace-generate-visualization", action="store_true", help="No generar visualizacion")
    return parser


async def main() -> None:
    args = build_parser().parse_args()

    result = await debug_normalize_from_paths(
        image_path=args.image,
        profile_source=args.profile_source,
        compare_image_path=args.compare_image,
        compare_profile_json_path=args.compare_profile_json,
        trace_patient_name=args.name,
        trace_patient_lastname=args.lastname,
        trace_sex=args.sex,
        trace_age=args.age,
        trace_weight=args.weight,
        trace_timestamp=args.timestamp,
        debug_save_json=True if args.debug_save_json else None,
        trace_generate_visualization=(
            False if args.no_trace_generate_visualization else (True if args.trace_generate_visualization else None)
        ),
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
