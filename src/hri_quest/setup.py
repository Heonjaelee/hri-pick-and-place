from setuptools import setup
package_name = 'hri_quest'
setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    entry_points={'console_scripts': [
        'quest_bridge_node = hri_quest.quest_bridge_node:main',
        'stream_node = hri_quest.stream_node:main',
    ]},
)
