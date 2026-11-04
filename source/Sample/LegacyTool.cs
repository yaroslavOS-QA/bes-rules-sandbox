namespace Sample
{
    // Legacy code: the BES_ prefix and the name-based parameter lookup are
    // recorded in tools/CheckRules/baseline.json, so they do not fail the check.
    // Adding one more such line (or a new file like this) must fail it.
    internal sealed class BES_LegacyTool
    {
        public object Read(dynamic element)
        {
            return element.LookupParameter("Comments");
        }
    }
}
