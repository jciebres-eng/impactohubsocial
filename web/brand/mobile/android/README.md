# Android launcher assets

Os PNGs `mipmap-{mdpi..xxxhdpi}/ic_launcher.png` seguem tamanhos 48/72/96/144/192 px. O XML adaptativo e vector foreground ficam em `adaptive-icon/` como fontes de integração; copie `ic_launcher.xml` para `res/mipmap-anydpi-v26/ic_launcher.xml`, `ic_launcher_foreground.xml` para `res/drawable/ic_launcher_foreground.xml` e `colors.xml` para `res/values/colors.xml`. O adaptive XML usa `@drawable/ic_launcher_foreground` e `@color/ic_launcher_background`.

O foreground deve ocupar zona segura central da grade 108 dp. As versões raster de fallback são assets quadrados; validar masks circulares/squircle em emulador. `ic_launcher_foreground.svg` é master de referência, o XML vector é recurso compilável. Este arquivo não foi compilado via Android Gradle nesta auditoria.
