# OfferForge 自动化测试

在项目根目录运行：

```powershell
python -m unittest discover -s tests -v
```

这些测试只使用内存请求和临时目录，不调用真实 AI，不写真实业务数据。
