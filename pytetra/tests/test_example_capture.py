import contextlib
import io
import unittest
from pathlib import Path

from pytetra.cli import main


class ExampleCaptureTestCase(unittest.TestCase):
    def test_public_example_decodes_to_mac_and_mm(self):
        capture = Path(__file__).parents[1] / "examples" / "example.bits"
        self.assertEqual(capture.stat().st_size, 200 * 510)

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main([str(capture)])

        text = output.getvalue()
        self.assertEqual(result, 0)
        self.assertEqual(
            text.count("Layer 2 - MAC(MacResourcePdu); SSI(101)"),
            199,
        )
        self.assertEqual(
            text.count("Layer 3 - MM(DLocationUpdateAccept); SSI(101)"),
            199,
        )


if __name__ == "__main__":
    unittest.main()
