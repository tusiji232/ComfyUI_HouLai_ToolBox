class AnyType(str):
    """Wildcard type for ComfyUI sockets."""

    def __ne__(self, __value: object) -> bool:
        return False


ANY_TYPE = AnyType("*")


class HouLai_Reroute:
    """
    Minimal pass-through relay node.
    - One input, one output
    - No transformation, only routing
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "optional": {
                "input": (ANY_TYPE, {"lazy": True}),
            }
        }

    RETURN_TYPES = (ANY_TYPE,)
    RETURN_NAMES = ("output",)
    FUNCTION = "route"
    CATEGORY = "HouLai_ToolBox/Logic"

    def check_lazy_status(self, **kwargs):
        if "input" in kwargs:
            return ["input"]
        return []

    def route(self, input=None):
        return (input,)
