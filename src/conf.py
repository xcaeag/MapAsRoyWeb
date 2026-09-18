from dataclasses import dataclass, asdict
import json


@dataclass
class MapConf:
    """Class to store configuration for map creation."""

    """
        myvar = MapConf.from_json("")
        myvar.json()
    """
    baseLayer: str = "roy"
    width: int = 350
    xmin: float = 0.0
    ymin: float = 40.0
    xmax: float = 2.0
    ymax: float = 42.0

    @classmethod
    def from_json(cls, string: str):
        data: dict = json.loads(string)
        return cls(**data)

    @classmethod
    def from_file(cls, filename):
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            return cls(**data)

    def json(self):
        return json.dumps(self, default=lambda o: o.__dict__)

    def to_file(self, filename):
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("ERR saveJson", filename)
            raise e


if __name__ == "__main__":
    mc = MapConf()
    mc.to_file("tmp.json")
    mc2 = MapConf.from_file("tmp.json")
    print(mc2)
