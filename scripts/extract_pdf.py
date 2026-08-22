from pypdf import PdfReader
import pathlib

SRC = pathlib.Path(r"C:/Users/Mcius/Desktop/Set_Theory")
for name, tag in [("Execise_1-15_Logic and Set Theory", "exercises"),
                  ("Lecture_1-15_Logic_and_Set_Theory", "lecture")]:
    r = PdfReader(str(SRC / (name + ".pdf")))
    text = "\n".join((p.extract_text() or "") for p in r.pages)
    out = pathlib.Path(__file__).parent / f"extracted_{tag}.txt"
    out.write_text(text, encoding="utf-8")
    print(out.name, len(r.pages), "pages,", len(text), "chars")
