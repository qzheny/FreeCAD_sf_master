
add_subdirectory(App)
if(FREECAD_BUILD_GUI)
    add_subdirectory(Gui)
endif(FREECAD_BUILD_GUI)

INSTALL(
    FILES
        Init.py
        InitGui.py
        BuildRegularGeoms.py
        App/MeshTestsApp.py
    DESTINATION
        Mod/Mesh
)
